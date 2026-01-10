"""LLM processor for job descriptions using NVIDIA NIM API."""

import os
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Rate limiting: 40 RPM per key, 3 keys = 120 RPM total
RATE_LIMIT_PER_KEY = 40
RATE_WINDOW_SECONDS = 60
# Number of parallel workers (higher than API keys to account for response time)
MAX_WORKERS = 10


@dataclass
class APIKey:
    """Represents an API key with rate limiting state."""
    key: str
    name: str
    request_times: deque  # timestamps of recent requests


class KeyRotator:
    """Manages rotation between multiple API keys with rate limiting."""

    def __init__(self):
        self.keys: List[APIKey] = []
        self.lock = threading.Lock()
        self._load_keys()

    def _load_keys(self):
        """Load API keys from environment."""
        key_names = [
            ("NVIDIA_API_KEY", "key1"),
            ("NVIDIA_API_KEY2", "key2"),
            ("NVIDIA_API_KEY3", "key3"),
        ]

        for env_name, name in key_names:
            key = os.getenv(env_name)
            if key:
                self.keys.append(APIKey(
                    key=key,
                    name=name,
                    request_times=deque(maxlen=RATE_LIMIT_PER_KEY)
                ))

        if not self.keys:
            raise ValueError("No NVIDIA API keys found in environment")

        print(f"[LLM] Loaded {len(self.keys)} API keys")

    def _clean_old_requests(self, api_key: APIKey):
        """Remove requests older than the rate window."""
        current_time = time.time()
        while api_key.request_times and (current_time - api_key.request_times[0]) > RATE_WINDOW_SECONDS:
            api_key.request_times.popleft()

    def get_available_key(self) -> Optional[Tuple[str, str]]:
        """Get an available API key that's under rate limit. Returns (key, name) or None."""
        with self.lock:
            current_time = time.time()

            for api_key in self.keys:
                self._clean_old_requests(api_key)

                if len(api_key.request_times) < RATE_LIMIT_PER_KEY:
                    api_key.request_times.append(current_time)
                    return api_key.key, api_key.name

            return None

    def get_wait_time(self) -> float:
        """Get seconds to wait until a key becomes available."""
        with self.lock:
            current_time = time.time()
            min_wait = float('inf')

            for api_key in self.keys:
                self._clean_old_requests(api_key)

                if len(api_key.request_times) < RATE_LIMIT_PER_KEY:
                    return 0

                if api_key.request_times:
                    oldest = api_key.request_times[0]
                    wait = RATE_WINDOW_SECONDS - (current_time - oldest)
                    min_wait = min(min_wait, max(0, wait))

            return min_wait if min_wait != float('inf') else 1.0

    def get_status(self) -> Dict:
        """Get current rate limit status for all keys."""
        with self.lock:
            status = {}
            for api_key in self.keys:
                self._clean_old_requests(api_key)
                status[api_key.name] = {
                    'used': len(api_key.request_times),
                    'limit': RATE_LIMIT_PER_KEY,
                    'available': RATE_LIMIT_PER_KEY - len(api_key.request_times)
                }
            return status


class JobDescriptionProcessor:
    """Processes job descriptions using NVIDIA NIM LLM."""

    MODEL = "moonshotai/kimi-k2-instruct-0905"
    BASE_URL = "https://integrate.api.nvidia.com/v1"

    SYSTEM_PROMPT = """You are a job description processor. Your task is to analyze job descriptions and produce structured output.

IMPORTANT: You must preserve ALL information from the original description. Do not omit, summarize, or change any details.

For each job description, provide a JSON response with these fields:

1. "cleaned_description": A well-formatted, readable version of the job description that:
   - Uses proper markdown formatting (headers, bullet points, paragraphs)
   - Fixes any HTML artifacts, encoding issues, or messy formatting
   - Organizes information logically (overview, responsibilities, requirements, benefits)
   - Preserves EVERY piece of information from the original
   - Does NOT add new information or opinions

2. "tags": An array of relevant tags (5-15 tags) including:
   - Technical skills (e.g., "Python", "AWS", "Kubernetes")
   - Job type (e.g., "Remote", "Hybrid", "On-site")
   - Experience level (e.g., "Senior", "Mid-level", "Entry-level")
   - Industry/domain (e.g., "FinTech", "Healthcare", "E-commerce")
   - Other relevant categorizations

3. "entities": An object containing extracted entities:
   - "companies": Array of company names mentioned (including hiring company, clients, partners)
   - "urls": Array of URLs found in the description
   - "emails": Array of email addresses
   - "phone_numbers": Array of phone numbers
   - "locations": Array of specific locations/addresses
   - "salary_info": Any salary/rate information found
   - "technologies": Array of specific technologies, tools, frameworks mentioned
   - "certifications": Array of certifications mentioned
   - "contact_persons": Array of recruiter/contact names

Respond ONLY with valid JSON, no markdown code blocks or other text."""

    def __init__(self):
        self.key_rotator = KeyRotator()

    def _create_client(self, api_key: str) -> OpenAI:
        """Create OpenAI client with given API key."""
        return OpenAI(
            base_url=self.BASE_URL,
            api_key=api_key
        )

    def _call_llm(self, description: str, job_title: str, company: str) -> Optional[Dict]:
        """Call the LLM API with rate limiting and key rotation."""
        # Wait for available key
        max_wait_time = 120  # Max 2 minutes wait
        total_waited = 0

        while total_waited < max_wait_time:
            result = self.key_rotator.get_available_key()
            if result:
                api_key, key_name = result
                break

            wait_time = min(self.key_rotator.get_wait_time(), 0.5)  # Quick retry
            if wait_time > 0.1:
                print(f"[LLM] Rate limited, waiting {wait_time:.1f}s...")
            time.sleep(wait_time)
            total_waited += wait_time
        else:
            print("[LLM] Timeout waiting for available API key")
            return None

        print(f"[LLM] Using {key_name} for: {job_title[:50]}...")

        user_prompt = f"""Process this job description:

Job Title: {job_title}
Company: {company}

Description:
{description}"""

        try:
            client = self._create_client(api_key)
            completion = client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                top_p=0.9,
                max_tokens=4096,
                stream=True
            )

            # Collect response
            full_response = ""
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content

            # Parse JSON response
            try:
                # Clean up response - remove any markdown code blocks
                response_text = full_response.strip()
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                response_text = response_text.strip()

                result = json.loads(response_text)
                return result
            except json.JSONDecodeError as e:
                print(f"[LLM] Failed to parse JSON response: {e}")
                print(f"[LLM] Response was: {full_response[:500]}...")
                return None

        except Exception as e:
            print(f"[LLM] API error: {e}")
            return None

    def process_job(self, job: Dict) -> Optional[Dict]:
        """Process a single job and return LLM results."""
        description = job.get('description', '')
        title = job.get('title', 'Unknown')
        company = job.get('company', 'Unknown')

        if not description or len(description) < 50:
            print(f"[LLM] Skipping job {job.get('id')} - description too short")
            return None

        result = self._call_llm(description, title, company)

        if result:
            return {
                'cleaned_description': result.get('cleaned_description', description),
                'tags': json.dumps(result.get('tags', [])),
                'entities': json.dumps(result.get('entities', {}))
            }

        return None

    def process_jobs_batch(self, jobs: List[Dict], progress_callback=None) -> Dict:
        """Process a batch of jobs in parallel. Returns stats."""
        stats = {'processed': 0, 'failed': 0, 'skipped': 0}
        stats_lock = threading.Lock()
        processed_count = [0]  # Use list for mutability in closure

        def process_single_job(job: Dict) -> Tuple[Dict, Optional[Dict]]:
            """Process a single job and return (job, result)."""
            return job, self.process_job(job)

        # Use ThreadPoolExecutor for parallel processing
        # MAX_WORKERS matches API key count for optimal throughput
        num_workers = min(MAX_WORKERS, len(jobs))

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit all jobs
            future_to_job = {executor.submit(process_single_job, job): job for job in jobs}

            for future in as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    job, result = future.result()

                    with stats_lock:
                        processed_count[0] += 1
                        if progress_callback:
                            progress_callback(processed_count[0], len(jobs), job.get('title', 'Unknown'))

                        if result:
                            stats['processed'] += 1
                            job['llm_result'] = result
                        else:
                            if len(job.get('description', '')) < 50:
                                stats['skipped'] += 1
                            else:
                                stats['failed'] += 1
                except Exception as e:
                    with stats_lock:
                        stats['failed'] += 1
                        print(f"[LLM] Error processing job {job.get('id')}: {e}")

        return stats

    def get_rate_limit_status(self) -> Dict:
        """Get current rate limit status."""
        return self.key_rotator.get_status()


# Singleton instance
_processor = None


def get_processor() -> JobDescriptionProcessor:
    """Get or create the processor singleton."""
    global _processor
    if _processor is None:
        _processor = JobDescriptionProcessor()
    return _processor
