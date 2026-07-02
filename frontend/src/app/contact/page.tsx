'use client';
import { useState } from 'react';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Phone, Mail, Send, CheckCircle2, AlertCircle } from 'lucide-react';
import { analyticsAPI, extractApiErrorMessage } from '@/lib/api';

export default function ContactPage() {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [subject, setSubject] = useState('');
    const [message, setMessage] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [success, setSuccess] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!message.trim()) return;

        setSubmitting(true);
        setError(null);
        setSuccess(false);

        try {
            await analyticsAPI.contactUs({
                name: name.trim(),
                email: email.trim(),
                subject: subject.trim() || 'Contact Support Request',
                message: message.trim(),
            });
            setSuccess(true);
            setName('');
            setEmail('');
            setSubject('');
            setMessage('');
        } catch (err: unknown) {
            const apiError = err as { response?: { data?: unknown } };
            if (apiError.response?.data) {
                setError(extractApiErrorMessage(apiError.response.data, 'Failed to send message. Please try again.'));
            } else {
                setError('Failed to send message. Please check your connection and try again.');
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container space-y-6 pb-8">
                    <div>
                        <h1 className="text-3xl font-extrabold tracking-tight text-foreground">Contact Us</h1>
                        <p className="text-sm text-muted-foreground mt-1">
                            Get in touch with CrackLabs support and UPSC CMS team. We typically respond within 2-4 hours.
                        </p>
                    </div>

                    <div className="grid md:grid-cols-5 gap-6">
                        {/* Contact Details Column */}
                        <div className="md:col-span-2 space-y-4">
                            <Card className="border-border/80 bg-card/70 shadow-sm backdrop-blur-sm">
                                <CardHeader>
                                    <CardTitle className="text-lg">Contact Info</CardTitle>
                                    <CardDescription>Reach out to us directly via phone or email.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <a 
                                        href="tel:9601981524" 
                                        className="flex items-center gap-3 p-3 rounded-xl border border-border/80 bg-muted/40 hover:bg-muted/70 hover:border-primary/40 transition-all group"
                                    >
                                        <div className="h-10 w-10 rounded-lg flex items-center justify-center bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 group-hover:scale-105 transition-transform">
                                            <Phone className="w-5 h-5" />
                                        </div>
                                        <div>
                                            <p className="text-xs text-muted-foreground">Phone / WhatsApp</p>
                                            <p className="text-sm font-semibold text-foreground">+91 9601981524</p>
                                        </div>
                                    </a>

                                    <a 
                                        href="mailto:crackwith.ai@gmail.com" 
                                        className="flex items-center gap-3 p-3 rounded-xl border border-border/80 bg-muted/40 hover:bg-muted/70 hover:border-primary/40 transition-all group"
                                    >
                                        <div className="h-10 w-10 rounded-lg flex items-center justify-center bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 group-hover:scale-105 transition-transform">
                                            <Mail className="w-5 h-5" />
                                        </div>
                                        <div>
                                            <p className="text-xs text-muted-foreground">Gmail Support</p>
                                            <p className="text-sm font-semibold text-foreground">crackwith.ai@gmail.com</p>
                                        </div>
                                    </a>
                                </CardContent>
                            </Card>

                            <Card className="border-border/80 bg-card/70 shadow-sm backdrop-blur-sm">
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-sm">Why contact us?</CardTitle>
                                </CardHeader>
                                <CardContent className="text-xs text-muted-foreground space-y-2">
                                    <p>🚀 <strong>Notes & Books request:</strong> Ask for specific books, custom handwritten notes, or high-yield lectures.</p>
                                    <p>⚡ <strong>Token Queries:</strong> Get support with token balances, bonus rewards, or payments.</p>
                                    <p>💡 <strong>Feedback:</strong> Tell us what features we should build next to help you crack the UPSC CMS exam!</p>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Contact Form Column */}
                        <div className="md:col-span-3">
                            <Card className="border-border/80 bg-card/85 shadow-sm backdrop-blur-sm">
                                <CardHeader>
                                    <CardTitle className="text-lg">Send Support Message</CardTitle>
                                    <CardDescription>All messages are forwarded directly to our expert CMS team.</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    {success ? (
                                        <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-6 text-center space-y-3">
                                            <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto" />
                                            <h4 className="text-lg font-bold text-emerald-500">Message Sent Successfully!</h4>
                                            <p className="text-sm text-muted-foreground">
                                                Thank you for reaching out. A copy of your inquiry has been sent to our coordinators.
                                            </p>
                                            <Button variant="outline" size="sm" onClick={() => setSuccess(false)}>
                                                Send Another Message
                                            </Button>
                                        </div>
                                    ) : (
                                        <form onSubmit={handleSubmit} className="space-y-4">
                                            {error && (
                                                <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive flex items-center gap-2">
                                                    <AlertCircle className="w-4 h-4 shrink-0" />
                                                    <span>{error}</span>
                                                </div>
                                            )}

                                            <div className="grid sm:grid-cols-2 gap-4">
                                                <div className="space-y-1.5">
                                                    <label htmlFor="contact-name" className="text-xs font-semibold text-muted-foreground">Your Name</label>
                                                    <Input 
                                                        id="contact-name" 
                                                        placeholder="Dr. Divyanshu" 
                                                        value={name} 
                                                        onChange={e => setName(e.target.value)} 
                                                    />
                                                </div>
                                                <div className="space-y-1.5">
                                                    <label htmlFor="contact-email" className="text-xs font-semibold text-muted-foreground">Your Email</label>
                                                    <Input 
                                                        id="contact-email" 
                                                        type="email" 
                                                        placeholder="name@college.edu" 
                                                        value={email} 
                                                        onChange={e => setEmail(e.target.value)} 
                                                    />
                                                </div>
                                            </div>

                                            <div className="space-y-1.5">
                                                <label htmlFor="contact-subject" className="text-xs font-semibold text-muted-foreground">Subject</label>
                                                <Input 
                                                    id="contact-subject" 
                                                    placeholder="Requesting Harrison 21st Edition PDF" 
                                                    value={subject} 
                                                    onChange={e => setSubject(e.target.value)} 
                                                />
                                            </div>

                                            <div className="space-y-1.5">
                                                <label htmlFor="contact-message" className="text-xs font-semibold text-muted-foreground">Message</label>
                                                <Textarea 
                                                    id="contact-message" 
                                                    placeholder="Provide details about your request or issue..." 
                                                    className="min-h-32"
                                                    value={message} 
                                                    onChange={e => setMessage(e.target.value)} 
                                                    required 
                                                />
                                            </div>

                                            <Button type="submit" className="w-full" disabled={submitting || !message.trim()}>
                                                <Send className="w-4 h-4 mr-2" />
                                                {submitting ? 'Sending inquiry...' : 'Send Support Request'}
                                            </Button>
                                        </form>
                                    )}
                                </CardContent>
                            </Card>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
