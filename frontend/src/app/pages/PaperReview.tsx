/**
 * PaperReview — Displays a literature review for a specific paper
 * Data is retrieved from sessionStorage
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { Layout } from '../components/Layout';
import { LiteratureReviewViewer } from '../components/LiteratureReviewViewer';
import { motion } from 'motion/react';
import { AlertCircle, ArrowLeft } from 'lucide-react';
import type { Paper } from '../../api/client';

interface ReviewData {
    review: string;
    citedPapers: Paper[];
    paper: Paper;
}

export function PaperReview() {
    const navigate = useNavigate();
    const [reviewData, setReviewData] = useState<ReviewData | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        try {
            const stored = sessionStorage.getItem('paperReview');
            if (stored) {
                const data = JSON.parse(stored) as ReviewData;
                setReviewData(data);
            } else {
                setError('No review data found. Please select a paper from Deep Research.');
            }
        } catch (err) {
            setError('Failed to load review data');
            console.error(err);
        }
    }, []);

    if (error) {
        return (
            <Layout showBack>
                <div style={{ maxWidth: '1320px', margin: '0 auto', padding: 'clamp(24px, 5vw, 32px) 24px 100px' }}>
                    <motion.div
                        initial={{ opacity: 0, y: 14 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4 }}
                        style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: '14px',
                            padding: '16px 18px',
                            borderRadius: '12px',
                            background: 'rgba(255,71,87,0.07)',
                            border: '1px solid rgba(255,71,87,0.22)',
                        }}
                    >
                        <AlertCircle size={18} color="#ff4757" style={{ flexShrink: 0, marginTop: '2px' }} />
                        <div style={{ flex: 1 }}>
                            <p style={{ fontSize: '14px', fontWeight: 600, color: '#ff4757', margin: '0 0 4px' }}>
                                Error Loading Review
                            </p>
                            <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.5)', margin: 0, lineHeight: 1.6 }}>
                                {error}
                            </p>
                            <button
                                onClick={() => navigate('/deep-research')}
                                style={{
                                    marginTop: '12px',
                                    padding: '8px 16px',
                                    borderRadius: '8px',
                                    background: 'rgba(124,58,237,0.15)',
                                    border: '1px solid rgba(124,58,237,0.35)',
                                    color: '#a78bfa',
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                    transition: 'all 0.15s',
                                }}
                                onMouseEnter={e => {
                                    (e.currentTarget as HTMLElement).style.background = 'rgba(124,58,237,0.25)';
                                }}
                                onMouseLeave={e => {
                                    (e.currentTarget as HTMLElement).style.background = 'rgba(124,58,237,0.15)';
                                }}
                            >
                                Return to Deep Research
                            </button>
                        </div>
                    </motion.div>
                </div>
            </Layout>
        );
    }

    if (!reviewData) {
        return (
            <Layout showBack>
                <div style={{ maxWidth: '1320px', margin: '0 auto', padding: 'clamp(24px, 5vw, 32px) 24px 100px' }}>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.4 }}
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            minHeight: '300px',
                            gap: '16px',
                        }}
                    >
                        <div style={{
                            width: '48px',
                            height: '48px',
                            borderRadius: '12px',
                            background: 'rgba(124,58,237,0.1)',
                            border: '1px solid rgba(124,58,237,0.2)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                        }}>
                            <span style={{
                                width: '24px',
                                height: '24px',
                                border: '2px solid rgba(255,255,255,0.2)',
                                borderTopColor: 'rgba(167,139,250,0.8)',
                                borderRadius: '50%',
                                animation: 'spin 0.8s linear infinite',
                                display: 'inline-block',
                            }} />
                        </div>
                        <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.4)' }}>Loading review…</p>
                    </motion.div>
                </div>
            </Layout>
        );
    }

    return (
        <Layout showBack>
            <div style={{ maxWidth: '1320px', margin: '0 auto', padding: 'clamp(24px, 5vw, 32px) 24px 100px' }}>
                <motion.div
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4 }}
                    style={{ marginBottom: 'clamp(24px, 5vw, 32px)' }}
                >
                    {/* Header with back button */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
                        <button
                            onClick={() => window.close()}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                width: '36px',
                                height: '36px',
                                borderRadius: '10px',
                                background: 'rgba(255,255,255,0.04)',
                                border: '1px solid rgba(255,255,255,0.09)',
                                color: 'rgba(255,255,255,0.4)',
                                cursor: 'pointer',
                                transition: 'all 0.15s',
                            }}
                            onMouseEnter={e => {
                                (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)';
                                (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.75)';
                            }}
                            onMouseLeave={e => {
                                (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
                                (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.4)';
                            }}
                            title="Close this tab"
                        >
                            <ArrowLeft size={16} />
                        </button>
                        <div>
                            <p style={{
                                fontSize: 'clamp(12px, 2vw, 14px)',
                                color: 'rgba(255,255,255,0.35)',
                                margin: 0,
                                textTransform: 'uppercase',
                                letterSpacing: '0.08em',
                                fontWeight: 600,
                            }}>
                                Paper Review
                            </p>
                            <h1 style={{
                                fontSize: 'clamp(18px, 4vw, 28px)',
                                fontWeight: 700,
                                color: 'rgba(255,255,255,0.9)',
                                margin: '4px 0 0',
                                fontFamily: "'Space Grotesk', sans-serif",
                                lineHeight: 1.3,
                                maxWidth: '800px',
                            }}>
                                {reviewData.paper.title}
                            </h1>
                        </div>
                    </div>

                    {/* Review viewer */}
                    <LiteratureReviewViewer
                        reviewText={reviewData.review}
                        citedPapers={reviewData.citedPapers}
                    />
                </motion.div>
            </div>

            <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
        </Layout>
    );
}
