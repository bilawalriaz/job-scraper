import { useState, useEffect, useCallback } from 'react';
import { getVoiceProfile, saveVoiceProfile } from '../api/client';
import { Card, CardHeader, CardBody } from '../components/Card';
import Button from '../components/Button';
import Spinner from '../components/Spinner';
import { CheckIcon } from '../components/Icons';

const PROMPTS = [
    {
        key: 'achievement_example',
        title: 'How do you describe achievements?',
        placeholder: 'Example: "Led a team of 5 engineers to deliver a cloud migration project 2 weeks ahead of schedule, resulting in 40% cost reduction..."',
        hint: 'Write 2-3 sentences describing an achievement you\'re proud of. This helps us understand how you quantify success and your preferred vocabulary.'
    },
    {
        key: 'problem_solved',
        title: 'How do you explain solving problems?',
        placeholder: 'Example: "When our deployment pipeline kept failing, I investigated the root cause, identified a race condition in our test suite, and implemented a fix that reduced build times by 60%..."',
        hint: 'Describe how you approached and solved a technical challenge. This shows your problem-solving communication style.'
    },
    {
        key: 'why_interested',
        title: 'Why are you looking for new opportunities?',
        placeholder: 'Example: "I\'m looking to take on more architectural responsibility and work with cutting-edge AI technologies in a product-focused environment..."',
        hint: 'Write this as you would in a cover letter. This captures your motivation framing and career narrative.'
    },
    {
        key: 'strengths_description',
        title: 'How do you describe your key strengths?',
        placeholder: 'Example: "I bring a unique combination of deep technical expertise in cloud platforms and strong stakeholder management skills, having regularly presented to C-level executives..."',
        hint: 'How would you present your strengths to a hiring manager? This shows how you position yourself.'
    },
    {
        key: 'collaboration_style',
        title: 'How do you describe working with others?',
        placeholder: 'Example: "I thrive in cross-functional teams, often bridging the gap between technical and business stakeholders. I believe in clear communication and proactive knowledge sharing..."',
        hint: 'Describe your collaboration and teamwork style. This captures how you talk about interpersonal skills.'
    }
];

function VoiceProfile() {
    const [profile, setProfile] = useState({
        achievement_example: '',
        problem_solved: '',
        why_interested: '',
        strengths_description: '',
        collaboration_style: '',
        tone: 'professional',
        formality: 'formal',
        avoid_phrases: ''
    });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    const loadProfile = useCallback(async () => {
        try {
            const data = await getVoiceProfile();
            if (data.profile) {
                setProfile(prev => ({ ...prev, ...data.profile }));
            }
        } catch (error) {
            console.error('Failed to load profile:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadProfile();
    }, [loadProfile]);

    const handleChange = (key, value) => {
        setProfile(prev => ({ ...prev, [key]: value }));
        setSaved(false);
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            await saveVoiceProfile(profile);
            setSaved(true);
            setTimeout(() => setSaved(false), 3000);
        } catch (error) {
            console.error('Failed to save profile:', error);
            alert('Failed to save: ' + error.message);
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="loading-state">
                <Spinner size={40} />
            </div>
        );
    }

    return (
        <>
            {/* Page Header */}
            <div className="page-header">
                <div>
                    <h1 className="page-title">Writing Voice</h1>
                    <p className="page-subtitle">Help us write cover letters that sound like you</p>
                </div>
                <Button
                    variant="primary"
                    onClick={handleSave}
                    loading={saving}
                    disabled={saving}
                >
                    {saved ? <><CheckIcon /> Saved</> : 'Save Profile'}
                </Button>
            </div>

            {/* Guided Prompts */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {PROMPTS.map((prompt) => (
                    <Card key={prompt.key}>
                        <CardHeader>{prompt.title}</CardHeader>
                        <CardBody>
                            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
                                {prompt.hint}
                            </p>
                            <textarea
                                className="form-control"
                                rows={4}
                                value={profile[prompt.key] || ''}
                                onChange={(e) => handleChange(prompt.key, e.target.value)}
                                placeholder={prompt.placeholder}
                                style={{ resize: 'vertical' }}
                            />
                        </CardBody>
                    </Card>
                ))}

                {/* Style Preferences */}
                <Card>
                    <CardHeader>Style Preferences</CardHeader>
                    <CardBody>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                            <div className="form-group">
                                <label className="form-label">Tone</label>
                                <select
                                    className="form-select"
                                    value={profile.tone}
                                    onChange={(e) => handleChange('tone', e.target.value)}
                                >
                                    <option value="professional">Professional</option>
                                    <option value="friendly">Friendly</option>
                                    <option value="confident">Confident</option>
                                </select>
                                <p style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                                    The overall tone of your communications
                                </p>
                            </div>
                            <div className="form-group">
                                <label className="form-label">Formality</label>
                                <select
                                    className="form-select"
                                    value={profile.formality}
                                    onChange={(e) => handleChange('formality', e.target.value)}
                                >
                                    <option value="formal">Formal</option>
                                    <option value="conversational">Conversational</option>
                                </select>
                                <p style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                                    How formal your writing should be
                                </p>
                            </div>
                        </div>
                        <div className="form-group" style={{ marginTop: '1rem' }}>
                            <label className="form-label">Phrases to Avoid</label>
                            <input
                                type="text"
                                className="form-control"
                                value={profile.avoid_phrases}
                                onChange={(e) => handleChange('avoid_phrases', e.target.value)}
                                placeholder='e.g., "utilize", "synergy", "leverage", "rockstar"'
                            />
                            <p style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                                Comma-separated list of words or phrases you dislike
                            </p>
                        </div>
                    </CardBody>
                </Card>
            </div>
        </>
    );
}

export default VoiceProfile;
