/**
 * JobStatusTracker — Real-time polling UI for async deep-research jobs.
 * Polls /api/deep-research/status/{jobId} every 5 s and renders a live
 * terminal-style progress feed.
 */

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { CheckCircle2, XCircle, Loader2, Clock, Zap, Database, FileSearch, BookOpen } from 'lucide-react';
import { getDeepResearchStatus, type DeepResearchJobStatus } from '../../api/client';

interface JobStatusTrackerProps {
  jobId: string;
  onComplete: (result: DeepResearchJobStatus) => void;
  onError: (error: string) => void;
}

const STEP_ICONS = [
  { icon: Zap, label: 'Generating search queries', key: 'generated_queries' },
  { icon: FileSearch, label: 'Retrieving papers', key: 'query_metadata' },
  { icon: Database, label: 'Scoring & filtering papers', key: 'accepted_papers' },
  { icon: BookOpen, label: 'Synthesising literature review', key: 'literature_review' },
];

function getStepIndex(status: DeepResearchJobStatus): number {
  if (status.literature_review) return 4;
  if (status.accepted_papers?.length) return 3;
  if (status.query_metadata?.length) return 2;
  if (status.generated_queries?.length) return 1;
  return 0;
}

export function JobStatusTracker({ jobId, onComplete, onError }: JobStatusTrackerProps) {
  const [status, setStatus] = useState<DeepResearchJobStatus | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollCount = useRef(0);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Elapsed time ticker
  useEffect(() => {
    timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  // Polling
  useEffect(() => {
    let backoff = 5000;

    let stopped = false;

    const poll = async () => {
      if (stopped) return;
      try {
        const data = await getDeepResearchStatus(jobId);
        if (stopped) return; // component may have unmounted while awaiting
        setStatus(data);

        // Build log messages from progress
        setLogs(prev => {
          const next = [...prev];
          if (data.generated_queries?.length && !prev.some(l => l.includes('queries generated')))
            next.push(`✓ ${data.generated_queries.length} search queries generated`);
          if (data.mesh_terms?.length && !prev.some(l => l.includes('MeSH terms')))
            next.push(`✓ MeSH terms extracted: ${data.mesh_terms.slice(0, 4).join(', ')}`);
          if (data.query_metadata?.length && !prev.some(l => l.includes('retrieved')))
            next.push(`✓ ${data.scored_papers?.length ?? '?'} candidate papers retrieved`);
          if (data.accepted_papers?.length && !prev.some(l => l.includes('accepted')))
            next.push(`✓ ${data.accepted_papers.length} papers accepted (tier ≥ threshold)`);
          return next;
        });

        if (data.status === 'completed') {
          stopped = true;
          if (intervalRef.current) clearInterval(intervalRef.current);
          if (timerRef.current) clearInterval(timerRef.current);
          onComplete(data);
          return;
        }
        if (data.status === 'failed') {
          stopped = true;
          if (intervalRef.current) clearInterval(intervalRef.current);
          if (timerRef.current) clearInterval(timerRef.current);
          onError(data.message || 'Job failed. Please try again.');
          return;
        }

        // Adaptive backoff after 30 polls
        pollCount.current += 1;
        if (pollCount.current > 30) backoff = Math.min(backoff * 1.5, 15000);
      } catch {
        // Silently back off on network errors
        backoff = Math.min(backoff * 2, 20000);
      }
    };

    // Set interval ref BEFORE the immediate poll so clearInterval inside poll
    // always has a valid reference to cancel (avoids stale-interval race condition).
    intervalRef.current = setInterval(poll, backoff);
    poll(); // Immediate first poll
    return () => {
      stopped = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [jobId]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const fmt = (s: number) => `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;
  const step = status ? getStepIndex(status) : 0;
  const isFailed = status?.status === 'failed';
  const isDone = status?.status === 'completed';

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      style={{
        borderRadius: '16px',
        background: 'rgba(255,255,255,0.025)',
        border: '1px solid rgba(255,255,255,0.08)',
        overflow: 'hidden',
      }}
    >
      {/* Header bar */}
      <div style={{
        padding: '14px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'rgba(255,255,255,0.02)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isDone ? (
            <CheckCircle2 size={16} color="#00e676" />
          ) : isFailed ? (
            <XCircle size={16} color="#ff4757" />
          ) : (
            <Loader2 size={16} color="#7c3aed" style={{ animation: 'spin 1s linear infinite' }} />
          )}
          <span style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: '13px', fontWeight: 600,
            color: isDone ? '#00e676' : isFailed ? '#ff4757' : 'rgba(255,255,255,0.8)',
          }}>
            {isDone ? 'Research complete' : isFailed ? 'Research failed' : 'Research in progress…'}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Clock size={12} color="rgba(255,255,255,0.3)" />
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '12px', color: 'rgba(255,255,255,0.35)',
          }}>
            {fmt(elapsed)}
          </span>
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '10px', padding: '2px 8px',
            borderRadius: '5px',
            background: isDone ? 'rgba(0,230,118,0.1)' : isFailed ? 'rgba(255,71,87,0.1)' : 'rgba(124,58,237,0.1)',
            border: `1px solid ${isDone ? 'rgba(0,230,118,0.25)' : isFailed ? 'rgba(255,71,87,0.25)' : 'rgba(124,58,237,0.25)'}`,
            color: isDone ? '#00e676' : isFailed ? '#ff4757' : '#a78bfa',
          }}>
            {status?.status ?? 'pending'}
          </span>
        </div>
      </div>

      {/* Steps */}
      <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {STEP_ICONS.map(({ icon: Icon, label }, i) => {
          const done = i < step;
          const active = i === step && !isDone && !isFailed;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: 28, height: 28, borderRadius: '8px', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: done || isDone
                  ? 'rgba(0,230,118,0.1)'
                  : active
                    ? 'rgba(124,58,237,0.15)'
                    : 'rgba(255,255,255,0.04)',
                border: `1px solid ${done || isDone ? 'rgba(0,230,118,0.3)' : active ? 'rgba(124,58,237,0.4)' : 'rgba(255,255,255,0.08)'}`,
                transition: 'all 0.4s',
              }}>
                {done || isDone
                  ? <CheckCircle2 size={13} color="#00e676" />
                  : active
                    ? <Icon size={13} color="#a78bfa" />
                    : <Icon size={13} color="rgba(255,255,255,0.2)" />
                }
              </div>
              <div style={{ flex: 1 }}>
                <span style={{
                  fontSize: '12px', fontWeight: 500,
                  color: done || isDone
                    ? 'rgba(255,255,255,0.7)'
                    : active
                      ? 'rgba(255,255,255,0.9)'
                      : 'rgba(255,255,255,0.25)',
                  transition: 'color 0.4s',
                }}>
                  {label}
                </span>
                {/* Shimmer bar for active step */}
                {active && (
                  <div style={{ marginTop: '4px', height: '2px', borderRadius: '2px', overflow: 'hidden', background: 'rgba(255,255,255,0.05)' }}>
                    <div className="ts-skeleton" style={{ height: '100%', width: '60%', background: 'linear-gradient(90deg, transparent, rgba(124,58,237,0.6), transparent)', borderRadius: '2px' }} />
                  </div>
                )}
              </div>
              {/* Counts */}
              {(done || isDone) && (
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '10px', color: '#00e676',
                }}>
                  {i === 0 && `${status?.generated_queries?.length ?? 0} queries`}
                  {i === 1 && `${status?.scored_papers?.length ?? 0} papers`}
                  {i === 2 && `${status?.accepted_papers?.length ?? 0} accepted`}
                  {i === 3 && `${status?.literature_review ? '~' + status.literature_review.split(' ').length + ' words' : ''}`}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Terminal log panel */}
      {logs.length > 0 && (
        <div style={{
          margin: '0 16px 16px',
          borderRadius: '10px',
          background: 'rgba(0,0,0,0.3)',
          border: '1px solid rgba(255,255,255,0.05)',
          padding: '12px',
          maxHeight: '110px', overflowY: 'auto',
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          <AnimatePresence>
            {logs.map((log, i) => (
              <motion.p
                key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25 }}
                style={{ fontSize: '11px', color: '#00e676', margin: 0, lineHeight: 1.7 }}
              >
                {log}
              </motion.p>
            ))}
          </AnimatePresence>
          <div ref={logsEndRef} />
        </div>
      )}

      {/* Job ID footer */}
      <div style={{
        padding: '10px 20px',
        borderTop: '1px solid rgba(255,255,255,0.04)',
        display: 'flex', alignItems: 'center', gap: '6px',
      }}>
        <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)' }}>JOB</span>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '10px', color: 'rgba(255,255,255,0.25)',
        }}>
          {jobId}
        </span>
      </div>
    </motion.div>
  );
}
