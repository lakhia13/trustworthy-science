export type Tier = 'trusted' | 'caution' | 'untrusted';

export interface Flag {
  code: string;
  pts: number;
  explanation: string;
  evidence: string;
}

export interface Dimensions {
  retraction: number;
  statistics: number;
  reproducibility: number;
  citations: number;
  methodology: number;
  venue: number;
}

export interface Paper {
  id: string;
  title: string;
  venue: string;
  year: number;
  doi: string;
  score: number;
  tier: Tier;
  hardFlags: string[];
  softFlags: Flag[];
  qualitySignals: Flag[];
  dimensions: Dimensions;
  verdict: string;
  abstract: string;
  authors: string;
}

export const PAPERS: Paper[] = [
  {
    id: 'p1',
    title: 'Marine ω-3 Fatty Acids and Prevention of Cardiovascular Disease and Cancer',
    venue: 'New England Journal of Medicine',
    year: 2019,
    doi: '10.1056/NEJMoa1811403',
    score: 78,
    tier: 'trusted',
    hardFlags: [],
    softFlags: [
      {
        code: 'VENUE_NOT_IN_DOAJ',
        pts: -2,
        explanation: 'Journal is paywalled and not indexed in the DOAJ open-access directory.',
        evidence: 'ISSN 0028-4793 — not found in DOAJ index as of 2024.'
      },
      {
        code: 'NO_PREREGISTRATION',
        pts: -1,
        explanation: 'No ClinicalTrials.gov registration ID found in abstract or methods section.',
        evidence: 'PubMed metadata search: no trial registration number detected.'
      }
    ],
    qualitySignals: [
      {
        code: 'DIVERSE_CITATIONS',
        pts: 4,
        explanation: '>50% institutional diversity among citing papers.',
        evidence: 'OpenAlex diversity score: 0.64'
      },
      {
        code: 'COI_DISCLOSED',
        pts: 2,
        explanation: 'Conflict of interest statement present and complete.',
        evidence: 'Full COI disclosure found in supplementary materials section.'
      },
      {
        code: 'LARGE_RCT',
        pts: 3,
        explanation: 'Large randomized controlled trial with 25,871 participants.',
        evidence: 'n=25,871 enrolled; VITAL Trial, ClinicalTrials.gov NCT01169259.'
      }
    ],
    dimensions: { retraction: 100, statistics: 85, reproducibility: 80, citations: 95, methodology: 70, venue: 88 },
    verdict: 'Safe to include in drug-discovery hypothesis. Key findings are robust and widely replicated.',
    abstract: 'Randomized trial of 25,871 participants evaluating marine n-3 fatty acid supplementation on cardiovascular and cancer outcomes.',
    authors: 'Manson JE, Cook NR, Lee IM, et al.'
  },
  {
    id: 'p2',
    title: 'COVID-19 Breakthrough Findings: Novel Antiviral Mechanism Validated in Vitro',
    venue: 'OMICS: A Journal of Integrative Biology',
    year: 2021,
    doi: '10.1089/omi.2021.0099',
    score: 25,
    tier: 'untrusted',
    hardFlags: ['RETRACTED', 'PREDATORY_VENUE'],
    softFlags: [
      {
        code: 'P_HACKING_DETECTED',
        pts: -8,
        explanation: 'Multiple p-values just below 0.05 threshold across all primary endpoints. Probable p-hacking.',
        evidence: 'p=0.049, p=0.048, p=0.047 across three primary endpoints.'
      },
      {
        code: 'EXCESSIVE_SELF_CITATION',
        pts: -5,
        explanation: '40% of citations reference the same first author\'s prior work.',
        evidence: 'Citation network analysis: 12 of 30 references are first-author self-citations.'
      }
    ],
    qualitySignals: [],
    dimensions: { retraction: 0, statistics: 15, reproducibility: 20, citations: 25, methodology: 30, venue: 10 },
    verdict: 'Exclude from analysis entirely. This paper has been retracted and was published in a predatory venue.',
    abstract: 'Claims novel antiviral mechanism but subsequently retracted due to fabricated data and predatory venue of publication.',
    authors: 'Smith J, Doe A, Jones B, et al.'
  },
  {
    id: 'p3',
    title: 'GLP-1 Receptor Agonists in Type 2 Diabetes: A Preregistered Meta-Analysis of 12 RCTs',
    venue: 'PLOS Medicine',
    year: 2023,
    doi: '10.1371/journal.pmed.1004123',
    score: 82,
    tier: 'trusted',
    hardFlags: [],
    softFlags: [
      {
        code: 'LIMITED_SAMPLE',
        pts: -2,
        explanation: 'Study sample size below recommended threshold for this endpoint meta-analysis.',
        evidence: 'n=847 across 12 studies; GRADE recommends n>1000 for this specific endpoint.'
      }
    ],
    qualitySignals: [
      {
        code: 'OPEN_DATA',
        pts: 6,
        explanation: 'Full dataset deposited in OSF repository with unrestricted access.',
        evidence: 'OSF repository: https://osf.io/abc123 — verified active.'
      },
      {
        code: 'PREREGISTERED',
        pts: 4,
        explanation: 'Systematic review preregistered in PROSPERO before data collection.',
        evidence: 'PROSPERO ID: CRD42022380641'
      },
      {
        code: 'OPEN_CODE',
        pts: 3,
        explanation: 'Full analysis code available on GitHub with reproducibility instructions.',
        evidence: 'GitHub: plos-medicine/glp1-meta — MIT licensed.'
      }
    ],
    dimensions: { retraction: 100, statistics: 88, reproducibility: 92, citations: 80, methodology: 85, venue: 90 },
    verdict: 'Safe to include in drug-discovery hypothesis. PLOS Medicine with full reproducibility package.',
    abstract: 'Preregistered meta-analysis of 12 RCTs evaluating GLP-1 receptor agonists for glycemic control and cardiovascular outcomes.',
    authors: 'Chen L, Williams R, Kumar A, et al.'
  },
  {
    id: 'p4',
    title: 'GLP-1 Signaling in Metabolic Disease: Mechanistic Insights from Adipose Tissue',
    venue: 'Journal of Clinical Endocrinology & Metabolism',
    year: 2022,
    doi: '10.1210/clinem/dgac123',
    score: 62,
    tier: 'caution',
    hardFlags: [],
    softFlags: [
      {
        code: 'NO_DATA_DEPOSIT',
        pts: -3,
        explanation: 'No public data repository linked in methods or supplementary materials.',
        evidence: 'PubMed metadata: no data availability statement found.'
      },
      {
        code: 'INDUSTRY_FUNDING',
        pts: -4,
        explanation: 'Study funded by pharmaceutical company with direct commercial interest in results.',
        evidence: 'Funding: Novo Nordisk A/S, grant #NN-2022-001.'
      }
    ],
    qualitySignals: [
      {
        code: 'COI_DISCLOSED',
        pts: 2,
        explanation: 'Conflict of interest clearly disclosed in funding statement.',
        evidence: 'Authors fully disclose funding from Novo Nordisk.'
      },
      {
        code: 'REPLICATED',
        pts: 5,
        explanation: 'Core mechanism replicated in two independent laboratories.',
        evidence: 'Replication: DOI 10.1210/clinem/dgac456; DOI 10.1016/j.metabol.2022.09.012'
      }
    ],
    dimensions: { retraction: 100, statistics: 65, reproducibility: 55, citations: 70, methodology: 60, venue: 72 },
    verdict: 'Verify key claims before relying on this. Industry funding and missing data deposit raise concerns.',
    abstract: 'Mechanistic investigation of GLP-1 receptor signaling in adipose tissue and hepatic glucose metabolism.',
    authors: 'Rodriguez M, Park H, Tanaka Y, et al.'
  },
  {
    id: 'p5',
    title: 'The GLP-1 Miracle: Curing Obesity and Type 2 Diabetes in 30 Days — A Clinical Validation',
    venue: 'International Journal of Medical Sciences (OMICS Group)',
    year: 2021,
    doi: '10.7150/ijms.99999',
    score: 18,
    tier: 'untrusted',
    hardFlags: ['PREDATORY_VENUE', 'FAILED_REPLICATION'],
    softFlags: [
      {
        code: 'P_HACKING_DETECTED',
        pts: -8,
        explanation: 'Implausible effect sizes across all endpoints; p-values appear manipulated.',
        evidence: 'All 7 endpoints show p<0.001 with impossibly small confidence intervals.'
      },
      {
        code: 'NO_ETHICS_APPROVAL',
        pts: -5,
        explanation: 'No ethics committee approval number in methods section.',
        evidence: 'Methods section: no IRB/ethics committee statement found after full-text analysis.'
      }
    ],
    qualitySignals: [],
    dimensions: { retraction: 60, statistics: 5, reproducibility: 10, citations: 20, methodology: 15, venue: 5 },
    verdict: 'Exclude from analysis. Predatory venue, failed replication, and implausible effect sizes.',
    abstract: 'Claims dramatic 30-day cure of obesity. Published in predatory journal; independent replication completely failed.',
    authors: 'Anonymous A, Anonymous B.'
  },
  {
    id: 'p6',
    title: 'CRISPR-Cas9 Off-Target Effects in Human Embryonic Stem Cells: A Genome-Wide Analysis',
    venue: 'Nature Biotechnology',
    year: 2022,
    doi: '10.1038/s41587-022-01223-1',
    score: 71,
    tier: 'trusted',
    hardFlags: [],
    softFlags: [
      {
        code: 'SMALL_N',
        pts: -3,
        explanation: 'Findings based on a relatively small number of cell lines (n=6).',
        evidence: 'Methods: 6 independent hESC lines; larger validation study recommended.'
      },
      {
        code: 'NO_PREREGISTRATION',
        pts: -1,
        explanation: 'Experimental laboratory study without preregistration.',
        evidence: 'No preregistration found on OSF or ClinicalTrials.gov.'
      }
    ],
    qualitySignals: [
      {
        code: 'DIVERSE_CITATIONS',
        pts: 3,
        explanation: '>60% institutional diversity in citation network analysis.',
        evidence: 'OpenAlex diversity score: 0.71'
      },
      {
        code: 'TOP_VENUE',
        pts: 5,
        explanation: 'Published in Nature Biotechnology — top-tier venue (IF=46.9).',
        evidence: 'Journal Impact Factor 2023: 46.9; SJR quartile Q1.'
      }
    ],
    dimensions: { retraction: 100, statistics: 78, reproducibility: 65, citations: 82, methodology: 72, venue: 98 },
    verdict: 'Safe to include. Nature Biotechnology publication with strong citation diversity. Minor concerns on sample size.',
    abstract: 'Genome-wide off-target analysis of CRISPR-Cas9 editing in human embryonic stem cells using GUIDE-seq and Digenome-seq.',
    authors: 'Kim D, Bae S, Park J, et al.'
  }
];

export const RECENT_SEARCHES = [
  { id: 'rs1', query: 'CRISPR off-target effects in hESC', paperCount: 3, date: '2026-04-17' },
  { id: 'rs2', query: 'GLP-1 receptor agonists metabolic disease', paperCount: 12, date: '2026-04-16' },
  { id: 'rs3', query: 'PCSK9 inhibitors cardiovascular events', paperCount: 8, date: '2026-04-15' },
];

export const TIER_CONFIG = {
  trusted: {
    label: 'Trusted',
    color: '#00e676',
    bg: 'rgba(0, 230, 118, 0.08)',
    border: 'rgba(0, 230, 118, 0.25)',
    glow: 'rgba(0, 230, 118, 0.15)',
  },
  caution: {
    label: 'Caution',
    color: '#ffd166',
    bg: 'rgba(255, 209, 102, 0.08)',
    border: 'rgba(255, 209, 102, 0.25)',
    glow: 'rgba(255, 209, 102, 0.15)',
  },
  untrusted: {
    label: 'Untrusted',
    color: '#ff4757',
    bg: 'rgba(255, 71, 87, 0.08)',
    border: 'rgba(255, 71, 87, 0.25)',
    glow: 'rgba(255, 71, 87, 0.15)',
  },
};
