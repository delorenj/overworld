#!/usr/bin/env python3
"""
End-to-end test for Overworld map generation.
Tests the complete flow: upload document → generate map → verify output.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx


API_BASE = "http://localhost:8778/api/v1"
TEST_USER_ID = 1  # The user we just created


async def create_test_document():
    """Create a test markdown document."""
    content = """# Project Alpha

## Sprint 1: Foundation
### Task 1.1: Setup Infrastructure
- Database setup
- API framework
- CI/CD pipeline

### Task 1.2: Core Models
- User model
- Document model
- Map model

## Sprint 2: Map Generation
### Task 2.1: Parser Agent
- Extract hierarchy from markdown
- L0-L4 level detection
- Metadata extraction

### Task 2.2: Artist Agent
- Generate map tiles
- Texture selection
- Color palette

## Sprint 3: Rendering
### Task 3.1: PixiJS Integration
- Canvas setup
- Sprite loading
- Viewport control

### Task 3.2: Interactions
- Zoom/pan
- Click handlers
- Tooltips
"""
    
    doc_path = Path("/tmp/test_doc.md")
    doc_path.write_text(content)
    return doc_path


async def upload_document(doc_path: Path):
    """Upload document via API (bypassing auth for now)."""
    print(f"📤 Uploading document: {doc_path}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        with open(doc_path, "rb") as f:
            files = {"file": (doc_path.name, f, "text/markdown")}
            response = await client.post(
                f"{API_BASE}/documents/upload",
                files=files
            )
        
        if response.status_code != 201:
            print(f"❌ Upload failed: {response.status_code}")
            print(response.text)
            return None
        
        data = response.json()
        doc_id = data["document_id"]
        print(f"✅ Document uploaded: {doc_id}")
        print(f"   Size: {data['size_bytes']} bytes")
        print(f"   Hash: {data['content_hash'][:16]}...")
        return doc_id


async def create_generation_job(document_id: str):
    """Create a map generation job (requires mocking auth)."""
    print(f"\n🎨 Creating generation job for document {document_id}")
    
    # This will fail without auth - we need to manually insert into DB
    # or patch the API to accept test mode
    # For now, let's insert directly via psql
    return None


async def create_job_via_db(document_id: str):
    """Create generation job directly in database."""
    import subprocess
    
    print(f"\n🎨 Creating generation job via database...")
    
    sql = f"""
    INSERT INTO generation_jobs (
        document_id, user_id, status, agent_state, progress_pct, created_at
    ) VALUES (
        '{document_id}', {TEST_USER_ID}, 'PENDING', '{{}}', 0.0, NOW()
    ) RETURNING id;
    """
    
    result = subprocess.run(
        [
            "docker", "compose", "-f", "/home/delorenj/code/overworld/compose.yml",
            "exec", "-T", "-e", "PGPASSWORD=Ittr5eesol",
            "postgres", "psql", "-U", "delorenj", "-d", "overworld",
            "-c", sql
        ],
        capture_output=True,
        text=True,
        cwd="/home/delorenj/code/overworld"
    )
    
    if result.returncode != 0:
        print(f"❌ Failed to create job: {result.stderr}")
        return None
    
    # Parse job ID from output
    lines = result.stdout.strip().split("\n")
    for line in lines:
        if line.strip().isdigit():
            job_id = int(line.strip())
            print(f"✅ Job created: #{job_id}")
            return job_id
    
    return None


async def publish_to_rabbitmq(job_id: int, document_id: str):
    """Publish job message to RabbitMQ."""
    import subprocess
    
    print(f"\n📨 Publishing job #{job_id} to RabbitMQ...")
    
    message = {
        "job_id": job_id,
        "arq_job_id": f"test-{job_id}",
        "document_id": document_id,
        "user_id": TEST_USER_ID,
        "options": {},
        "retry_count": 0,
        "max_retries": 3
    }
    
    # Use rabbitmqadmin or Python pika library
    # For simplicity, let's use docker exec with python
    python_code = f"""
import pika
import json

params = pika.URLParameters('amqp://delorenj:Ittr5eesol@rabbitmq:5672/')
connection = pika.BlockingConnection(params)
channel = connection.channel()

# Don't declare queue - use existing one
message_json = json.dumps({json.dumps(message)})
channel.basic_publish(
    exchange='',
    routing_key='generation.pending',
    body=message_json.encode('utf-8'),
    properties=pika.BasicProperties(
        delivery_mode=2,  # make message persistent
    )
)

print("Message published")
connection.close()
"""
    
    result = subprocess.run(
        [
            "docker", "compose", "-f", "/home/delorenj/code/overworld/compose.yml",
            "exec", "-T", "backend", "python", "-c", python_code
        ],
        capture_output=True,
        text=True,
        cwd="/home/delorenj/code/overworld"
    )
    
    if result.returncode != 0:
        print(f"❌ Failed to publish: {result.stderr}")
        return False
    
    print(f"✅ Message published to queue")
    return True


async def monitor_job(job_id: int, timeout=120):
    """Monitor job status until completion."""
    import subprocess
    
    print(f"\n👀 Monitoring job #{job_id} (timeout: {timeout}s)")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < timeout:
        sql = f"SELECT status, progress_pct, error_msg FROM generation_jobs WHERE id = {job_id};"
        
        result = subprocess.run(
            [
                "docker", "compose", "-f", "/home/delorenj/code/overworld/compose.yml",
                "exec", "-T", "-e", "PGPASSWORD=Ittr5eesol",
                "postgres", "psql", "-U", "delorenj", "-d", "overworld",
                "-t", "-c", sql
            ],
            capture_output=True,
            text=True,
            cwd="/home/delorenj/code/overworld"
        )
        
        if result.returncode == 0 and result.stdout.strip():
            parts = [p.strip() for p in result.stdout.strip().split("|")]
            if len(parts) >= 2:
                status, progress = parts[0], parts[1]
                
                if status != last_status:
                    print(f"   Status: {status} ({progress}%)")
                    last_status = status
                
                if status in ["completed", "failed", "cancelled"]:
                    if status == "completed":
                        print(f"✅ Job completed!")
                        return True
                    else:
                        error = parts[2] if len(parts) > 2 else "Unknown error"
                        print(f"❌ Job {status}: {error}")
                        return False
        
        await asyncio.sleep(2)
    
    print(f"⏱️ Timeout reached")
    return False


async def verify_output(job_id: int):
    """Verify the generated map output."""
    import subprocess
    
    print(f"\n🔍 Verifying output for job #{job_id}")
    
    sql = f"""
    SELECT m.id, m.filename, m.width, m.height 
    FROM maps m 
    JOIN generation_jobs gj ON m.id = gj.map_id 
    WHERE gj.id = {job_id};
    """
    
    result = subprocess.run(
        [
            "docker", "compose", "-f", "/home/delorenj/code/overworld/compose.yml",
            "exec", "-T", "-e", "PGPASSWORD=Ittr5eesol",
            "postgres", "psql", "-U", "delorenj", "-d", "overworld",
            "-c", sql
        ],
        capture_output=True,
        text=True,
        cwd="/home/delorenj/code/overworld"
    )
    
    print(result.stdout)
    
    if "1 row" in result.stdout or "(1 row)" in result.stdout:
        print("✅ Map record found in database")
        return True
    else:
        print("❌ No map record found")
        return False


async def main():
    """Run end-to-end test."""
    print("🗺️  Overworld E2E Map Generation Test")
    print("=" * 50)
    
    # Step 1: Create test document
    doc_path = await create_test_document()
    print(f"✅ Created test document: {doc_path}")
    
    # Step 2: Upload document
    doc_id = await upload_document(doc_path)
    if not doc_id:
        print("❌ Upload failed, aborting")
        return 1
    
    # Step 3: Create generation job
    job_id = await create_job_via_db(doc_id)
    if not job_id:
        print("❌ Job creation failed, aborting")
        return 1
    
    # Step 4: Publish to queue
    published = await publish_to_rabbitmq(job_id, doc_id)
    if not published:
        print("❌ Queue publish failed, aborting")
        return 1
    
    # Step 5: Monitor job
    success = await monitor_job(job_id)
    if not success:
        print("\n❌ Job did not complete successfully")
        return 1
    
    # Step 6: Verify output
    verified = await verify_output(job_id)
    
    print("\n" + "=" * 50)
    if verified:
        print("✅ E2E TEST PASSED")
        print(f"   Document ID: {doc_id}")
        print(f"   Job ID: {job_id}")
        return 0
    else:
        print("❌ E2E TEST FAILED - Output verification failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
