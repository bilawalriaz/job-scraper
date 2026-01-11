"""Centralized LLM prompts for CV parsing, job matching, and document generation."""

# ==================== CV PARSING ====================

CV_PARSE_PROMPT = """Parse this CV/resume text and extract structured information.

CV Text:
{cv_text}

Return a JSON object with these fields:

{{
    "personal_info": {{
        "name": "",
        "email": "",
        "phone": "",
        "location": "",
        "linkedin": ""
    }},
    "summary": "",
    "skills": {{
        "technical": [],
        "soft": [],
        "certifications": []
    }},
    "experience": [
        {{
            "title": "",
            "company": "",
            "dates": "",
            "duration_months": 0,
            "responsibilities": [],
            "achievements": [],
            "technologies_used": []
        }}
    ],
    "education": [
        {{
            "degree": "",
            "institution": "",
            "year": "",
            "details": ""
        }}
    ],
    "keywords": []
}}

IMPORTANT:
- Extract ALL information exactly as written
- Do not infer or add details not present
- For experience, separate responsibilities from achievements
- List technologies/tools in technologies_used
- Keywords should include searchable terms for job matching

Respond ONLY with valid JSON, no markdown code blocks."""


# ==================== JOB MATCHING ====================

JOB_MATCH_PROMPT = """Analyze how well this candidate matches the job requirements.

=== CANDIDATE CV ===
{cv_summary}

=== JOB DESCRIPTION ===
Title: {job_title}
Company: {company}
Location: {location}
Salary: {salary}

Description:
{job_description}

=== ANALYSIS REQUIRED ===
Provide a JSON response:

{{
    "match_score": 0-100,
    "recommendation": "Apply" | "Consider" | "Skip",
    "skills_matched": ["skill1", "skill2"],
    "skills_missing": ["skill3", "skill4"],
    "experience_fit": {{
        "years_required": "",
        "years_candidate": "",
        "relevant_roles": [],
        "gaps": []
    }},
    "strengths": ["strength1", "strength2"],
    "concerns": ["concern1"],
    "tailoring_tips": [
        "Emphasize X experience",
        "Highlight Y project",
        "Mention Z skill prominently"
    ],
    "summary": "2-3 sentence overall assessment"
}}

SCORING GUIDE:
- 80-100: Strong match, should definitely apply
- 60-79: Good match with some gaps, worth applying
- 40-59: Partial match, consider if very interested
- Below 40: Weak match, likely not suitable

Be honest and precise. Score based on actual match, not optimism.
Respond ONLY with valid JSON, no markdown code blocks."""


# ==================== CV TAILORING ====================

CV_TAILOR_PROMPT = """Rewrite this CV content to better match the target job while staying truthful.

=== ORIGINAL CV CONTENT ===
{original_content}

=== TARGET JOB ===
Title: {job_title}
Company: {company}
Key Requirements: {requirements}

=== VOICE PROFILE ===
Achievement style: {achievement_style}
Tone: {tone}
Formality: {formality}
Phrases to avoid: {avoid_phrases}

=== INSTRUCTIONS ===
1. Use keywords from the job description naturally
2. Reorder bullet points to highlight relevant experience first
3. Quantify achievements where data exists
4. Match the user's writing voice and style
5. DO NOT invent new experiences or skills
6. DO NOT exaggerate or misrepresent
7. Keep similar length to original

Return JSON:
{{
    "summary": "Tailored professional summary",
    "experience": [
        {{
            "title": "Same title",
            "company": "Same company",
            "dates": "Same dates",
            "bullets": ["Rewritten bullet 1", "Rewritten bullet 2"]
        }}
    ],
    "skills": {{
        "technical": ["Reordered to prioritize relevant skills"],
        "soft": ["Relevant soft skills"]
    }},
    "changes_made": [
        "Added keyword 'X' from job description",
        "Moved cloud experience to top",
        "Quantified team size in bullet 3"
    ]
}}

Respond ONLY with valid JSON, no markdown code blocks."""


# ==================== COVER LETTER ====================

COVER_LETTER_PROMPT = """Write a concise cover letter for this job application.

=== CANDIDATE PROFILE ===
Name: {name}
Summary: {summary}
Key Skills: {skills}
Recent Experience: {experience}

=== JOB DETAILS ===
Title: {job_title}
Company: {company}
Location: {location}
Key Requirements: {requirements}

=== VOICE PROFILE ===
How they describe achievements: {achievement_example}
How they explain problem-solving: {problem_solved}
Why seeking new opportunities: {why_interested}
Tone preference: {tone}
Formality: {formality}
Phrases to avoid: {avoid_phrases}

=== INSTRUCTIONS ===
Write 3-4 paragraphs (250-350 words total):

1. OPENING (2-3 sentences):
   - Hook related to company/role
   - Express genuine interest
   - Match the user's opening style from their examples

2. BODY (2 paragraphs):
   - Highlight 2-3 specific experiences matching requirements
   - Use concrete examples and outcomes
   - Mirror language from job description naturally
   - Match how the user describes their achievements

3. CLOSING (2-3 sentences):
   - Express enthusiasm
   - Clear call to action
   - Professional sign-off

CRITICAL:
- Match the user's writing voice from the profile samples
- Avoid generic phrases like "I am writing to apply for..."
- Be specific, not generic
- Don't use phrases the user wants to avoid
- Keep it concise - quality over quantity

Return JSON:
{{
    "cover_letter": "The full cover letter text with proper paragraphs",
    "key_points_highlighted": ["point1", "point2", "point3"],
    "job_keywords_used": ["keyword1", "keyword2"]
}}

Respond ONLY with valid JSON, no markdown code blocks."""


# ==================== VOICE ANALYSIS ====================

VOICE_ANALYSIS_PROMPT = """Analyze this writing sample to understand the author's voice and style.

=== WRITING SAMPLES ===
{writing_samples}

Analyze and return JSON:
{{
    "tone": "professional" | "friendly" | "confident" | "formal",
    "formality_level": "very_formal" | "formal" | "conversational" | "casual",
    "sentence_structure": "short_punchy" | "medium" | "long_complex",
    "vocabulary_level": "simple" | "moderate" | "advanced" | "technical",
    "common_patterns": [
        "Starts sentences with action verbs",
        "Uses specific metrics",
        "Avoids passive voice"
    ],
    "favorite_phrases": ["phrase1", "phrase2"],
    "style_notes": "Brief description of overall writing style"
}}

Respond ONLY with valid JSON, no markdown code blocks."""


# ==================== HELPER FUNCTIONS ====================

def format_cv_for_matching(cv_data: dict) -> str:
    """Format parsed CV data into a summary for matching."""
    parts = []

    # Personal info
    personal = cv_data.get('personal_info', {})
    if personal.get('name'):
        parts.append(f"Name: {personal['name']}")

    # Summary
    if cv_data.get('summary'):
        parts.append(f"\nSummary: {cv_data['summary']}")

    # Skills
    skills = cv_data.get('skills', {})
    if skills.get('technical'):
        parts.append(f"\nTechnical Skills: {', '.join(skills['technical'])}")
    if skills.get('certifications'):
        parts.append(f"Certifications: {', '.join(skills['certifications'])}")

    # Experience
    experience = cv_data.get('experience', [])
    if experience:
        parts.append("\nExperience:")
        for exp in experience[:3]:  # Top 3 most recent
            title = exp.get('title', 'Unknown')
            company = exp.get('company', '')
            dates = exp.get('dates', '')
            parts.append(f"- {title} at {company} ({dates})")
            achievements = exp.get('achievements', [])[:2]
            for ach in achievements:
                parts.append(f"  * {ach}")

    # Education
    education = cv_data.get('education', [])
    if education:
        parts.append("\nEducation:")
        for edu in education[:2]:
            degree = edu.get('degree', '')
            institution = edu.get('institution', '')
            parts.append(f"- {degree} from {institution}")

    return '\n'.join(parts)


def format_voice_profile_for_prompt(voice_profile: dict) -> dict:
    """Format voice profile for use in prompts."""
    return {
        'achievement_example': voice_profile.get('achievement_example', 'Not provided'),
        'problem_solved': voice_profile.get('problem_solved', 'Not provided'),
        'why_interested': voice_profile.get('why_interested', 'Not provided'),
        'tone': voice_profile.get('tone', 'professional'),
        'formality': voice_profile.get('formality', 'formal'),
        'avoid_phrases': voice_profile.get('avoid_phrases', '[]')
    }
