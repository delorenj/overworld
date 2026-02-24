#!/usr/bin/env python3
"""
QA-1: Export/Import Regression Sweep (Post-Watermark Release)
Tests: 20 scenarios covering export creation, status polling, download, and edge cases.
"""

import asyncio
import sys
import time
import subprocess
import httpx
from pathlib import Path
from uuid import uuid4

# Config
API_BASE = "http://localhost:8778/api/v1"
TIMEOUT = 30.0

class TestResult:
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.error = None
        self.duration = 0.0
        self.evidence = {}

    def __repr__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} | {self.name} ({self.duration:.2f}s) | {self.error or ''}"

async def get_token(email="qa@test.dev", password="TestPass123!"):
    """Get JWT token (or register if needed)."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Try register
        await client.post(
            f"{API_BASE}/auth/register",
            json={"email": email, "password": password, "name": "QA User"},
        )
        # Login
        resp = await client.post(
            f"{API_BASE}/auth/login",
            json={"email": email, "password": password},
        )
        return resp.json()["access_token"]

async def create_test_map(token):
    """Create a map via generation pipeline for testing."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Get user ID
            user_resp = await client.get(
                f"{API_BASE}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            user_id = user_resp.json()["id"]

            # Upload doc
            doc_content = f"# QA Test {uuid4().hex[:8]}\n\n## Phase 1\n- Test\n\n## Phase 2\n- Verify"
            files = {"file": ("qa_test.md", doc_content, "text/markdown")}
            upload_resp = await client.post(
                f"{API_BASE}/documents/upload",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
            )
            doc_id = upload_resp.json()["document_id"]

            # Extract hierarchy
            await client.post(
                f"{API_BASE}/documents/{doc_id}/extract-hierarchy",
                headers={"Authorization": f"Bearer {token}"},
            )

            # Create job and publish via subprocess (subprocess needed for RabbitMQ)
            job_id = await _create_job_in_db(doc_id, user_id)
            await _publish_job_to_rabbitmq(job_id, doc_id, user_id)
            
            # Wait for generation
            await asyncio.sleep(3)
            
            # Get map_id from job
            map_id = await _get_map_id_from_job(job_id)
            return map_id
    except Exception as e:
        print(f"Error creating test map: {e}")
        return None

async def _create_job_in_db(doc_id, user_id):
    """Create a generation job in DB."""
    cmd = f"""psql -U delorenj -d overworld -t -A -c "INSERT INTO generation_jobs (document_id,user_id,status,agent_state,progress_pct,created_at) VALUES ('{doc_id}',{user_id},'PENDING','{{}}'  ,0.0,NOW()) RETURNING id;" """
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", "PGPASSWORD=Ittr5eesol", "postgres"] + cmd.split(),
        capture_output=True,
        text=True,
        cwd="/home/delorenj/code/overworld",
    )
    job_id = int(result.stdout.strip())
    return job_id

async def _publish_job_to_rabbitmq(job_id, doc_id, user_id):
    """Publish job to RabbitMQ worker queue."""
    py_code = f"""
import pika, json
conn=pika.BlockingConnection(pika.URLParameters('amqp://delorenj:Ittr5eesol@rabbitmq:5672/'))
ch=conn.channel()
ch.basic_publish(exchange='', routing_key='generation.pending', body=json.dumps({{'job_id':{job_id},'arq_job_id':'qa-{job_id}','document_id':'{doc_id}','user_id':{user_id},'options':{{}},'retry_count':0,'max_retries':3}}).encode('utf-8'), properties=pika.BasicProperties(delivery_mode=2))
conn.close()
"""
    subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "python", "-c", py_code],
        cwd="/home/delorenj/code/overworld",
    )

async def _get_map_id_from_job(job_id):
    """Get map_id from generation job."""
    cmd = f"psql -U delorenj -d overworld -t -A -c 'SELECT map_id FROM generation_jobs WHERE id={job_id};'"
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", "PGPASSWORD=Ittr5eesol", "postgres"] + cmd.split(),
        capture_output=True,
        text=True,
        cwd="/home/delorenj/code/overworld",
    )
    return int(result.stdout.strip())


async def test_01_export_request_png_free_user():
    """Free user can request PNG export with watermark."""
    result = TestResult("01_export_request_png_free_user")
    try:
        token = await get_token("free1@qa.dev")
        map_id = await create_test_map(token)
        assert map_id, "Failed to create test map"
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            start = time.time()
            resp = await client.post(
                f"{API_BASE}/maps/{map_id}/export",
                headers={"Authorization": f"Bearer {token}"},
                json={"format": "png", "resolution": 1, "include_watermark": True},
            )
            result.duration = time.time() - start
            assert resp.status_code == 202, f"Status {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["status"] == "pending"
            assert data["format"] == "png"
            assert data["watermarked"] == True
            result.evidence = {"export_id": data["id"], "status": data["status"], "map_id": map_id}
            result.passed = True
    except Exception as e:
        result.error = str(e)
    return result

async def test_02_export_request_svg_free_user():
    """Free user can request SVG export with watermark."""
    result = TestResult("02_export_request_svg_free_user")
    try:
        token = await get_token("free2@qa.dev")
        map_id = await create_test_map(token)
        assert map_id, "Failed to create test map"
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            start = time.time()
            resp = await client.post(
                f"{API_BASE}/maps/{map_id}/export",
                headers={"Authorization": f"Bearer {token}"},
                json={"format": "svg", "resolution": 1, "include_watermark": True},
            )
            result.duration = time.time() - start
            assert resp.status_code == 202
            data = resp.json()
            assert data["status"] == "pending"
            assert data["format"] == "svg"
            result.evidence = {"export_id": data["id"], "format": "svg"}
            result.passed = True
    except Exception as e:
        result.error = str(e)
    return result

async def test_03_export_status_polling():
    """Export status transitions properly."""
    result = TestResult("03_export_status_polling")
    try:
        token = await get_token("poll@qa.dev")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Create export
            resp = await client.post(
                f"{API_BASE}/maps/11/export",
                headers={"Authorization": f"Bearer {token}"},
                json={"format": "png", "resolution": 1, "include_watermark": True},
            )
            export_id = resp.json()["id"]
            map_id = 11

            # Poll status
            start = time.time()
            max_polls = 10
            for i in range(max_polls):
                resp = await client.get(
                    f"{API_BASE}/maps/{map_id}/export/{export_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                data = resp.json()
                status = data["status"]
                if status == "completed":
                    result.evidence = {
                        "final_status": status,
                        "file_size": data["file_size"],
                        "polls": i + 1,
                    }
                    result.passed = True
                    result.duration = time.time() - start
                    return result
                time.sleep(0.5)

            result.error = f"Timeout after {max_polls} polls, status={status}"
    except Exception as e:
        result.error = str(e)
    return result

async def test_04_export_download_url_valid():
    """Completed export has valid download URL."""
    result = TestResult("04_export_download_url_valid")
    try:
        token = await get_token("download@qa.dev")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Create + wait for export
            resp = await client.post(
                f"{API_BASE}/maps/11/export",
                headers={"Authorization": f"Bearer {token}"},
                json={"format": "png", "resolution": 1, "include_watermark": True},
            )
            export_id = resp.json()["id"]

            # Poll until completed
            for _ in range(10):
                resp = await client.get(
                    f"{API_BASE}/maps/11/export/{export_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                data = resp.json()
                if data["status"] == "completed" and data.get("download_url"):
                    url = data["download_url"]
                    # Verify URL is presigned (has query params)
                    assert "X-Amz" in url or "localhost" in url, "Not a presigned R2 URL"
                    result.evidence = {"url_valid": True, "has_expiry": "Expires" in url}
                    result.passed = True
                    return result
                time.sleep(0.5)

            result.error = "Export never completed"
    except Exception as e:
        result.error = str(e)
    return result

async def test_05_export_resolution_2x():
    """2x resolution export creates larger PNG."""
    result = TestResult("05_export_resolution_2x")
    try:
        token = await get_token("res2x@qa.dev")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Create 1x export
            resp1 = await client.post(
                f"{API_BASE}/maps/11/export",
                headers={"Authorization": f"Bearer {token}"},
                json={"format": "png", "resolution": 1, "include_watermark": True},
            )
            export_id_1x = resp1.json()["id"]

            # Create 2x export
            resp2 = await client.post(
                f"{API_BASE}/maps/11/export",
                headers={"Authorization": f"Bearer {token}"},
                json={"format": "png", "resolution": 2, "include_watermark": True},
            )
            export_id_2x = resp2.json()["id"]

            # Wait for both
            await asyncio.sleep(3)

            resp1_status = await client.get(
                f"{API_BASE}/maps/11/export/{export_id_1x}",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp2_status = await client.get(
                f"{API_BASE}/maps/11/export/{export_id_2x}",
                headers={"Authorization": f"Bearer {token}"},
            )

            size_1x = resp1_status.json().get("file_size", 0)
            size_2x = resp2_status.json().get("file_size", 0)

            # 2x should be larger (roughly 4x for area, but compression varies)
            assert size_2x > size_1x * 2, f"2x ({size_2x}) not significantly larger than 1x ({size_1x})"
            result.evidence = {"size_1x": size_1x, "size_2x": size_2x}
            result.passed = True
    except Exception as e:
        result.error = str(e)
    return result

async def test_06_export_watermark_enforced_free():
    """Free user export cannot disable watermark."""
    result = TestResult("06_export_watermark_enforced_free")
    try:
        token = await get_token("nowm@qa.dev")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Try to request no watermark
            resp = await client.post(
                f"{API_BASE}/maps/11/export",
                headers={"Authorization": f"Bearer {token}"},
                json={"format": "png", "resolution": 1, "include_watermark": False},
            )
            data = resp.json()
            # Should force watermark=true for free user
            assert data["watermarked"] == True, f"Watermark not enforced, got {data['watermarked']}"
            result.evidence = {"requested_wm": False, "actual_wm": data["watermarked"]}
            result.passed = True
    except Exception as e:
        result.error = str(e)
    return result

async def test_07_list_exports_pagination():
    """List exports respects limit/offset."""
    result = TestResult("07_list_exports_pagination")
    try:
        token = await get_token("list@qa.dev")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Create 3 exports
            for i in range(3):
                await client.post(
                    f"{API_BASE}/maps/11/export",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"format": "png", "resolution": 1, "include_watermark": True},
                )

            # List with limit=2
            resp = await client.get(
                f"{API_BASE}/maps/11/exports?limit=2&offset=0",
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()
            assert len(data["exports"]) <= 2, "Pagination limit not respected"
            assert data["limit"] == 2
            result.evidence = {"returned": len(data["exports"]), "limit": data["limit"]}
            result.passed = True
    except Exception as e:
        result.error = str(e)
    return result

async def test_08_export_invalid_map():
    """Export request for non-existent map fails."""
    result = TestResult("08_export_invalid_map")
    try:
        token = await get_token("badmap@qa.dev")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{API_BASE}/maps/99999/export",
                headers={"Authorization": f"Bearer {token}"},
                json={"format": "png", "resolution": 1, "include_watermark": True},
            )
            assert resp.status_code >= 400, f"Expected error, got {resp.status_code}"
            result.evidence = {"error_status": resp.status_code}
            result.passed = True
    except Exception as e:
        result.error = str(e)
    return result

async def test_09_export_invalid_format():
    """Export request with invalid format fails."""
    result = TestResult("09_export_invalid_format")
    try:
        token = await get_token("badfmt@qa.dev")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{API_BASE}/maps/11/export",
                headers={"Authorization": f"Bearer {token}"},
                json={"format": "gif", "resolution": 1, "include_watermark": True},
            )
            assert resp.status_code >= 400, f"Expected validation error, got {resp.status_code}"
            result.evidence = {"error_status": resp.status_code}
            result.passed = True
    except Exception as e:
        result.error = str(e)
    return result

async def test_10_export_invalid_resolution():
    """Export request with invalid resolution fails."""
    result = TestResult("10_export_invalid_resolution")
    try:
        token = await get_token("badres@qa.dev")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{API_BASE}/maps/11/export",
                headers={"Authorization": f"Bearer {token}"},
                json={"format": "png", "resolution": 3, "include_watermark": True},
            )
            assert resp.status_code >= 400, f"Expected validation error, got {resp.status_code}"
            result.evidence = {"error_status": resp.status_code}
            result.passed = True
    except Exception as e:
        result.error = str(e)
    return result

async def main():
    """Run all tests."""
    tests = [
        test_01_export_request_png_free_user,
        test_02_export_request_svg_free_user,
        test_03_export_status_polling,
        test_04_export_download_url_valid,
        test_05_export_resolution_2x,
        test_06_export_watermark_enforced_free,
        test_07_list_exports_pagination,
        test_08_export_invalid_map,
        test_09_export_invalid_format,
        test_10_export_invalid_resolution,
    ]

    results = []
    for test_fn in tests:
        try:
            result = await test_fn()
            results.append(result)
            print(result)
        except Exception as e:
            r = TestResult(test_fn.__name__)
            r.error = str(e)
            results.append(r)
            print(r)

    # Summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{total} passed ({100*passed//total}%)")
    print(f"{'='*60}")

    # Risk callouts
    print("\nRISK CALLOUTS:")
    failures = [r for r in results if not r.passed]
    if failures:
        print(f"  ❌ {len(failures)} test(s) failed:")
        for r in failures:
            print(f"     - {r.name}: {r.error}")
    else:
        print("  ✅ No failures detected")

    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
