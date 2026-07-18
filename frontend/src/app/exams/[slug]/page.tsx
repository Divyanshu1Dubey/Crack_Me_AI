import { Metadata } from 'next';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Info, Target, Users, BookOpen, Clock, CalendarDays, CheckCircle2, ChevronRight } from 'lucide-react';
import Link from 'next/link';

// Static Data for the Exams
const examData = {
  'upsc-cms': {
    title: 'UPSC CMS (Combined Medical Services)',
    description: 'The Union Public Service Commission (UPSC) conducts the CMS Examination annually to recruit medical officers for various central government organizations like Railways, Ordnance Factories, and CGHS.',
    tags: ['Govt Job', 'Permanent', 'Class-I Officer'],
    eligibility: {
      qualification: 'Passed the written and practical parts of the final MBBS examination.',
      internship: 'Must be completed upon selection.',
      ageLimit: 'Under 32 years (relaxations apply).',
      nationality: 'Citizen of India (or specified subjects/refugees).'
    },
    pattern: {
      type: 'Computer-Based Test (CBT) + Personality Test',
      totalMarks: '500 Written + 100 Interview',
      duration: '2 hours per paper',
      negativeMarking: '-1/3rd penalty for wrong answers'
    },
    syllabus: [
      { name: 'Paper I', desc: 'General Medicine (96 Qs) & Paediatrics (24 Qs)', weightage: '250 Marks' },
      { name: 'Paper II', desc: 'Surgery, Gynaecology & Obstetrics, and PSM (40 Qs each)', weightage: '250 Marks' }
    ]
  },
  'neet-pg': {
    title: 'NEET PG',
    description: 'The National Eligibility cum Entrance Test (Postgraduate) is the single entrance examination for admission to various MD/MS and PG Diploma courses in India.',
    tags: ['Postgraduate', 'NBE', 'All India Level'],
    eligibility: {
      qualification: 'MBBS degree or Provisional Pass Certificate recognized by NMC.',
      internship: 'Must have completed a 1-year rotatory internship by the NBEMS cutoff date.',
      ageLimit: 'No specific age limit.',
      nationality: 'Indian citizens, OCI, and foreign nationals (with restrictions).'
    },
    pattern: {
      type: 'Computer-Based Test (CBT)',
      totalMarks: '800 Marks (200 MCQs)',
      duration: '3 hours and 30 minutes',
      negativeMarking: '+4 for Correct, -1 for Incorrect'
    },
    syllabus: [
      { name: 'Pre-Clinical', desc: 'Anatomy, Physiology, Biochemistry', weightage: 'Low-Medium' },
      { name: 'Para-Clinical', desc: 'Pathology, Pharmacology, Microbiology, Forensic Med, PSM', weightage: 'Medium-High' },
      { name: 'Clinical', desc: 'General Medicine, Surgery, Pediatrics, OBG, etc.', weightage: 'Highest' }
    ]
  },
  'ini-cet': {
    title: 'INI-CET (Institute of National Importance)',
    description: 'Combined entrance test for admission to PG courses (MD/MS/M.Ch/DM) at AIIMS, JIPMER, NIMHANS, PGIMER, and SCTIMST.',
    tags: ['Premium Institutes', 'AIIMS', 'Biannual'],
    eligibility: {
      qualification: 'Coming Soon - Data being fetched from official portals.',
      internship: 'Coming Soon - Data being fetched from official portals.',
      ageLimit: 'Coming Soon - Data being fetched from official portals.',
      nationality: 'Coming Soon - Data being fetched from official portals.'
    },
    pattern: {
      type: 'Coming Soon',
      totalMarks: 'Coming Soon',
      duration: 'Coming Soon',
      negativeMarking: 'Coming Soon'
    },
    syllabus: [
      { name: 'Full MBBS Syllabus', desc: 'Detailed breakdown coming soon.', weightage: 'N/A' }
    ]
  },
  'fmge': {
    title: 'FMGE (Foreign Medical Graduate Examination)',
    description: 'Screening test for Indian citizens possessing medical qualifications awarded by medical institutions outside India to practice in India.',
    tags: ['Screening Test', 'NBE', 'Biannual'],
    eligibility: {
      qualification: 'Coming Soon - Data being fetched from official portals.',
      internship: 'Coming Soon - Data being fetched from official portals.',
      ageLimit: 'Coming Soon - Data being fetched from official portals.',
      nationality: 'Coming Soon - Data being fetched from official portals.'
    },
    pattern: {
      type: 'Coming Soon',
      totalMarks: 'Coming Soon',
      duration: 'Coming Soon',
      negativeMarking: 'Coming Soon'
    },
    syllabus: [
      { name: 'Full MBBS Syllabus', desc: 'Detailed breakdown coming soon.', weightage: 'N/A' }
    ]
  }
};

type Props = {
  params: Promise<{ slug: string }>
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const resolvedParams = await params;
  const data = examData[resolvedParams.slug as keyof typeof examData];
  if (!data) return { title: 'Exam Not Found' };
  return {
    title: `${data.title} | CrackCMS Knowledge Base`,
    description: data.description,
  }
}

export default async function ExamPage({ params }: Props) {
  const resolvedParams = await params;
  const data = examData[resolvedParams.slug as keyof typeof examData];

  if (!data) {
    return (
      <div className="flex-1 p-8 text-center mt-20">
        <h1 className="text-3xl font-bold mb-4">Exam Not Found</h1>
        <Link href="/dashboard" className="text-primary hover:underline">Return to Dashboard</Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-20 pb-16 bg-muted/20">
      <div className="container mx-auto px-4 lg:px-8 max-w-5xl">
        
        {/* Header Section */}
        <div className="mb-8 border-b border-border/40 pb-8">
          <div className="flex flex-wrap gap-2 mb-4">
            {data.tags.map(tag => (
              <Badge key={tag} variant="secondary" className="bg-primary/10 text-primary hover:bg-primary/20 border-0">{tag}</Badge>
            ))}
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4 text-foreground">{data.title}</h1>
          <p className="text-lg text-muted-foreground leading-relaxed max-w-3xl">
            {data.description}
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          
          {/* Main Content Area */}
          <div className="md:col-span-2 space-y-8">
            
            {/* Eligibility */}
            <Card className="border-border/50 shadow-sm bg-card/60 backdrop-blur-sm">
              <CardHeader className="pb-3 border-b border-border/40 bg-muted/30">
                <CardTitle className="flex items-center gap-2 text-xl">
                  <CheckCircle2 className="w-5 h-5 text-emerald-500" /> Eligibility Criteria
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-6 space-y-4">
                <div className="flex gap-4 items-start">
                  <div className="bg-muted p-2 rounded-lg shrink-0 mt-0.5"><BookOpen className="w-4 h-4 text-muted-foreground" /></div>
                  <div>
                    <h4 className="font-semibold text-sm">Educational Qualification</h4>
                    <p className="text-muted-foreground text-sm mt-1">{data.eligibility.qualification}</p>
                  </div>
                </div>
                <div className="flex gap-4 items-start">
                  <div className="bg-muted p-2 rounded-lg shrink-0 mt-0.5"><Clock className="w-4 h-4 text-muted-foreground" /></div>
                  <div>
                    <h4 className="font-semibold text-sm">Internship Status</h4>
                    <p className="text-muted-foreground text-sm mt-1">{data.eligibility.internship}</p>
                  </div>
                </div>
                <div className="flex gap-4 items-start">
                  <div className="bg-muted p-2 rounded-lg shrink-0 mt-0.5"><Users className="w-4 h-4 text-muted-foreground" /></div>
                  <div>
                    <h4 className="font-semibold text-sm">Age Limit</h4>
                    <p className="text-muted-foreground text-sm mt-1">{data.eligibility.ageLimit}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Syllabus */}
            <Card className="border-border/50 shadow-sm bg-card/60 backdrop-blur-sm">
              <CardHeader className="pb-3 border-b border-border/40 bg-muted/30">
                <CardTitle className="flex items-center gap-2 text-xl">
                  <BookOpen className="w-5 h-5 text-blue-500" /> Syllabus Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-6">
                <div className="space-y-4">
                  {data.syllabus.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-center p-3 rounded-xl border border-border/60 hover:bg-muted/30 transition-colors">
                      <div>
                        <h4 className="font-semibold">{item.name}</h4>
                        <p className="text-xs text-muted-foreground mt-0.5">{item.desc}</p>
                      </div>
                      <Badge variant="outline" className="shrink-0">{item.weightage}</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <Card className="border-border/50 shadow-sm bg-gradient-to-br from-card to-muted/20">
              <CardHeader className="pb-3 border-b border-border/40">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Target className="w-4 h-4 text-amber-500" /> Exam Pattern
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-5 space-y-4 text-sm">
                <div>
                  <span className="text-muted-foreground block text-xs font-medium uppercase tracking-wider mb-1">Type</span>
                  <span className="font-semibold">{data.pattern.type}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-xs font-medium uppercase tracking-wider mb-1">Duration</span>
                  <span className="font-semibold">{data.pattern.duration}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-xs font-medium uppercase tracking-wider mb-1">Total Marks</span>
                  <span className="font-semibold">{data.pattern.totalMarks}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-xs font-medium uppercase tracking-wider mb-1">Negative Marking</span>
                  <span className="font-semibold text-rose-500">{data.pattern.negativeMarking}</span>
                </div>
              </CardContent>
            </Card>

            {data.eligibility.qualification.includes('Coming Soon') && (
              <Card className="border-primary/20 bg-primary/5 shadow-inner">
                <CardContent className="pt-6 text-center">
                  <Info className="w-8 h-8 text-primary mx-auto mb-3 opacity-80" />
                  <h3 className="font-semibold text-foreground mb-1">More Data Arriving Soon</h3>
                  <p className="text-xs text-muted-foreground mb-4">Our internet crawlers are actively gathering the latest official notifications.</p>
                  <div className="flex gap-2">
                    <input type="email" placeholder="Notify me" className="flex-1 bg-background border border-border rounded-lg px-3 text-xs" />
                    <button className="bg-primary text-primary-foreground px-3 py-1.5 rounded-lg text-xs font-semibold">Subscribe</button>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
