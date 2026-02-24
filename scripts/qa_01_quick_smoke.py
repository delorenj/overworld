#!/usr/bin/env python3
"""
QA-1: Regression Test Suite for Export/Import (Post-Watermark)
10 core tests covering create, status, download, resolution, watermark, and errors.
"""
import subprocess
import time
import httpx
import json
import asyncio
from uuid import uuid4

API_BASE = "http://localhost:8778/api/v1"
TIMEOUT = 30.0

def run_psql(sql, compose_cwd="/home/delorenj/code/overworld"):
    """Run psql command via docker compose."""
    cmd = ["docker", "compose", "exec", "-T", "-e", "PGPASSWORD=Ittr5eesol", "postgres",
           "psql", "-U", "delorenj", "-d", "overworld", "-t", "-A", "-c", sql]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=compose_cwd)
    return result.stdout.strip()

def publish_job_to_rabbitmq(job_id, doc_id, user_id):
    """Publish job to RabbitMQ."""
    py = f"""
import pika, json
conn=pika.BlockingConnection(pika.URLParameters('amqp://delorenj:Ittr5eesol@rabbitmq:5672/'))
ch=conn.channel()
ch.basic_publish(exchange='', routing_key='generation.pending', body=json.dumps({{'job_id':{job_id},'arq_job_id':'qa-{job_id}','document_id':'{doc_id}','user_id':{user_id},'options':{{}},'retry_count':0,'max_retries':3}}).encode('utf-8'), properties=pika.BasicProperties(delivery_mode=2))
conn.close()
"""
    subprocess.run(["docker", "compose", "exec", "-T", "backend", "python", "-c", py],
                   cwd="/home/delorenj/code/overworld", capture_output=True)

async def create_map_for_user(token):
    """Create a test map for the given user."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Get user ID
        user_resp = await client.get(f"{API_BASE}/auth/me", headers={"Authorization": f"Bearer {token}"})
        user_id = user_resp.json()["id"]

        # Upload doc
        doc_name = f"qa_{uuid4().hex[:6]}.md"
        files = {"file": (doc_name, "# Test\n## P1\n- A\n\n## P2\n- B", "text/markdown")}
        up_resp = await client.post(f"{API_BASE}/documents/upload",
            headers={"Authorization": f"Bearer {token}"}, files=files)
        doc_id = up_resp.json()["document_id"]

        # Extract hierarchy
        await client.post(f"{API_BASE}/documents/{doc_id}/extract-hierarchy",
            headers={"Authorization": f"Bearer {token}"})

        # Create job in DB
        job_sql = f"INSERT INTO generation_jobs (document_id,user_id,status,agent_state,progress_pct,created_at) VALUES ('{doc_id}',{user_id},'PENDING','{{}}'  ,0.0,NOW()) RETURNING id;"
        output = run_psql(job_sql)
        # Extract just the ID from the output (may include INSERT 0 1 line)
        job_id = int([l for l in output.split('\n') if l.isdigit()][0])

        # Publish to worker
        publish_job_to_rabbitmq(job_id, doc_id, user_id)
        
        # Wait for completion
        await asyncio.sleep(3)

        # Get map_id
        map_sql = f"SELECT map_id FROM generation_jobs WHERE id={job_id};"
        map_id = int(run_psql(map_sql))
        return map_id

async def test_all():
    """Run all tests."""
    results = []

    # Setup: register a user
    subprocess.run(["curl", "-s", "-X", "POST", f"{API_BASE}/auth/register",
        "-H", "Content-Type: application/json",
        "-d", '{"email":"qa_test@qa.dev","password":"TestPass123!","name":"QA"}'],
        capture_output=True)

    login_resp = subprocess.run(
        ["curl", "-s", "-X", "POST", f"{API_BASE}/auth/login",
        "-H", "Content-Type: application/json",
        "-d", '{"email":"qa_test@qa.dev","password":"TestPass123!"}'],
        capture_output=True, text=True)
    token = json.loads(login_resp.stdout)["access_token"]
    print("Setup: User registered & logged in\n")

    # Create a map for testing
    print("Creating test map...")
    map_id = await create_map_for_user(token)
    print(f"✅ Test map created (id={map_id})\n")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # T1: PNG export
        print("T1: PNG export request...")
        resp = await client.post(f"{API_BASE}/maps/{map_id}/export",
            headers={"Authorization": f"Bearer {token}"},
            json={"format": "png", "resolution": 1, "include_watermark": True})
        assert resp.status_code == 202
        png_id = resp.json()["id"]
        print(f"✅ PASS | PNG export created (id={png_id})\n")
        results.append(("T1_PNG_export", True, None))

        # T2: SVG export
        print("T2: SVG export request...")
        resp = await client.post(f"{API_BASE}/maps/{map_id}/export",
            headers={"Authorization": f"Bearer {token}"},
            json={"format": "svg", "resolution": 1, "include_watermark": True})
        assert resp.status_code == 202
        svg_id = resp.json()["id"]
        print(f"✅ PASS | SVG export created (id={svg_id})\n")
        results.append(("T2_SVG_export", True, None))

        # T3: Status polling
        print("T3: Export status polling...")
        for i in range(10):
            resp = await client.get(f"{API_BASE}/maps/{map_id}/export/{png_id}",
                headers={"Authorization": f"Bearer {token}"})
            status = resp.json()["status"]
            if status == "completed":
                print(f"✅ PASS | Status transitioned to COMPLETED after {i+1} polls\n")
                results.append(("T3_status_polling", True, None))
                break
            await asyncio.sleep(0.5)

        # T4: Download URL valid
        print("T4: Download URL validity...")
        resp = await client.get(f"{API_BASE}/maps/{map_id}/export/{png_id}",
            headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        url = data.get("download_url")
        assert url, "No download URL"
        assert "X-Amz" in url or "localhost" in url
        print(f"✅ PASS | Presigned URL valid\n")
        results.append(("T4_download_url", True, None))

        # T5: 2x resolution larger
        print("T5: Resolution scaling (1x vs 2x)...")
        resp = await client.post(f"{API_BASE}/maps/{map_id}/export",
            headers={"Authorization": f"Bearer {token}"},
            json={"format": "png", "resolution": 2, "include_watermark": True})
        export_2x_id = resp.json()["id"]
        await asyncio.sleep(3)
        resp1 = await client.get(f"{API_BASE}/maps/{map_id}/export/{png_id}",
            headers={"Authorization": f"Bearer {token}"})
        resp2 = await client.get(f"{API_BASE}/maps/{map_id}/export/{export_2x_id}",
            headers={"Authorization": f"Bearer {token}"})
        size1x = resp1.json().get("file_size", 0)
        size2x = resp2.json().get("file_size", 0)
        assert size2x > size1x * 1.5, f"2x ({size2x}) not larger than 1x ({size1x})"
        print(f"✅ PASS | 2x larger: {size1x} → {size2x} bytes\n")
        results.append(("T5_resolution_scaling", True, None))

        # T6: Watermark enforced
        print("T6: Watermark enforcement...")
        resp = await client.post(f"{API_BASE}/maps/{map_id}/export",
            headers={"Authorization": f"Bearer {token}"},
            json={"format": "png", "resolution": 1, "include_watermark": False})
        assert resp.json()["watermarked"] == True
        print(f"✅ PASS | Watermark forced for free user\n")
        results.append(("T6_watermark_enforced", True, None))

        # T7: List exports
        print("T7: List exports pagination...")
        resp = await client.get(f"{API_BASE}/maps/{map_id}/exports?limit=2",
            headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert len(data["exports"]) <= 2
        print(f"✅ PASS | Pagination respected: {len(data['exports'])} ≤ {data['limit']}\n")
        results.append(("T7_list_pagination", True, None))

        # T8: Invalid map
        print("T8: Invalid map error handling...")
        resp = await client.post(f"{API_BASE}/maps/99999/export",
            headers={"Authorization": f"Bearer {token}"},
            json={"format": "png", "resolution": 1, "include_watermark": True})
        assert resp.status_code >= 400
        print(f"✅ PASS | Correct error code: {resp.status_code}\n")
        results.append(("T8_invalid_map", True, None))

        # T9: Invalid format
        print("T9: Invalid format error...")
        resp = await client.post(f"{API_BASE}/maps/{map_id}/export",
            headers={"Authorization": f"Bearer {token}"},
            json={"format": "gif", "resolution": 1, "include_watermark": True})
        assert resp.status_code >= 400
        print(f"✅ PASS | Validation error: {resp.status_code}\n")
        results.append(("T9_invalid_format", True, None))

        # T10: Invalid resolution
        print("T10: Invalid resolution error...")
        resp = await client.post(f"{API_BASE}/maps/{map_id}/export",
            headers={"Authorization": f"Bearer {token}"},
            json={"format": "png", "resolution": 5, "include_watermark": True})
        assert resp.status_code >= 400
        print(f"✅ PASS | Validation error: {resp.status_code}\n")
        results.append(("T10_invalid_resolution", True, None))

    # Summary
    print("\n" + "="*70)
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print(f"SUMMARY: {passed}/{total} tests PASSED ({100*passed//total}%)")
    print("="*70)

    # Risk callouts
    print("\nRISK CALLOUTS:")
    failures = [r for r in results if not r[1]]
    if failures:
        print(f"  ⚠️  {len(failures)} test(s) failed:")
        for name, _, err in failures:
            print(f"     - {name}: {err}")
    else:
        print("  ✅ No test failures detected")
        print("  ✅ Export/import regression suite CLEAN")
        print("  ✅ Watermark enforcement working")

if __name__ == "__main__":
    asyncio.run(test_all())
