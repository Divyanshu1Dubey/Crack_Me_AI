'use client';

import React, { useLayoutEffect, useRef, useState, useEffect } from 'react';
import Link from 'next/link';
import { gsap } from 'gsap';
import { ArrowUpRight, ChevronRight, ChevronDown, Sparkles } from 'lucide-react';
import './CardNav.css';

type CardNavLink = {
  label: string;
  href: string;
  ariaLabel: string;
};

export type CardNavItem = {
  label: string;
  bgColor: string;
  textColor: string;
  links: CardNavLink[];
};

export interface CardNavProps {
  logoText?: string;
  items?: CardNavItem[];
  className?: string;
  ease?: string;
  themeToggleSlot?: React.ReactNode;
  isAuthenticated?: boolean;
}

const defaultItems: CardNavItem[] = [
  {
    label: "Question Banks",
    bgColor: "#1e293b",
    textColor: "#f8fafc",
    links: [
      { label: "UPSC CMS PYQ Atlas (2018-2025)", href: "/questions", ariaLabel: "UPSC CMS Question Bank" },
      { label: "NEET PG High-Yield QBank", href: "/neet-pg", ariaLabel: "NEET PG Question Bank" }
    ]
  },
  {
    label: "AI Tutor & Recall",
    bgColor: "#0f172a",
    textColor: "#f8fafc",
    links: [
      { label: "Harrison Trained AI Assistant", href: "/ai-tutor", ariaLabel: "AI Tutor Assistant" },
      { label: "Spaced Repetition Flashcards", href: "/flashcards", ariaLabel: "Rapid Recall Flashcards" }
    ]
  },
  {
    label: "Mocks & Analytics",
    bgColor: "#1e1b4b",
    textColor: "#f8fafc",
    links: [
      { label: "Adaptive CMS Mock Engine", href: "/tests", ariaLabel: "Adaptive Mock Tests" },
      { label: "Weak-Area Diagnostic Analytics", href: "/analytics", ariaLabel: "Performance Analytics" }
    ]
  }
];

const examOptions = [
  { id: 'cms', label: 'UPSC CMS', icon: '🩺', href: '/exams/cms' },
  { id: 'neet-pg', label: 'NEET PG', icon: '📚', href: '/exams/neet-pg' },
  { id: 'usmle', label: 'USMLE', icon: '🌍', href: '/exams/usmle' },
];

const CardNav: React.FC<CardNavProps> = ({
  logoText = 'crackCMS',
  items = defaultItems,
  className = '',
  ease = 'power3.out',
  themeToggleSlot,
  isAuthenticated = false
}) => {
  const [isHamburgerOpen, setIsHamburgerOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isExamDropdownOpen, setIsExamDropdownOpen] = useState(false);
  
  const navRef = useRef<HTMLDivElement | null>(null);
  const examDropdownRef = useRef<HTMLDivElement | null>(null);
  const cardsRef = useRef<HTMLDivElement[]>([]);
  const tlRef = useRef<gsap.core.Timeline | null>(null);

  // Click-outside & Keyboard navigation dismissal
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (examDropdownRef.current && !examDropdownRef.current.contains(e.target as Node)) {
        setIsExamDropdownOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsExamDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const handleExamSelect = (href: string) => {
    setIsExamDropdownOpen(false);
    setIsExpanded(false);
    setIsHamburgerOpen(false);

    const micrositesSection = document.getElementById('exam-microsites');
    if (micrositesSection) {
      micrositesSection.scrollIntoView({ behavior: 'smooth' });
    } else {
      window.location.href = href;
    }
  };

  const calculateHeight = () => {
    const navEl = navRef.current;
    if (!navEl) return 280;

    const isMobile = window.matchMedia('(max-width: 768px)').matches;
    if (isMobile) {
      const contentEl = navEl.querySelector('.card-nav-content') as HTMLElement;
      if (contentEl) {
        const wasVisible = contentEl.style.visibility;
        const wasPointerEvents = contentEl.style.pointerEvents;
        const wasPosition = contentEl.style.position;
        const wasHeight = contentEl.style.height;

        contentEl.style.visibility = 'visible';
        contentEl.style.pointerEvents = 'auto';
        contentEl.style.position = 'static';
        contentEl.style.height = 'auto';

        contentEl.offsetHeight;

        const topBar = 64;
        const padding = 16;
        const contentHeight = contentEl.scrollHeight;

        contentEl.style.visibility = wasVisible;
        contentEl.style.pointerEvents = wasPointerEvents;
        contentEl.style.position = wasPosition;
        contentEl.style.height = wasHeight;

        return topBar + contentHeight + padding;
      }
    }
    return 280;
  };

  const createTimeline = () => {
    const navEl = navRef.current;
    if (!navEl) return null;

    gsap.set(navEl, { height: 64, overflow: isExamDropdownOpen ? 'visible' : 'hidden' });
    gsap.set(cardsRef.current, { y: 40, opacity: 0 });

    const tl = gsap.timeline({ paused: true });

    tl.to(navEl, {
      height: calculateHeight,
      duration: 0.4,
      ease
    });

    tl.to(cardsRef.current, { y: 0, opacity: 1, duration: 0.4, ease, stagger: 0.08 }, '-=0.1');

    return tl;
  };

  useLayoutEffect(() => {
    const tl = createTimeline();
    tlRef.current = tl;

    return () => {
      tl?.kill();
      tlRef.current = null;
    };
  }, [ease, items]);

  useLayoutEffect(() => {
    const handleResize = () => {
      if (!tlRef.current) return;

      if (isExpanded) {
        const newHeight = calculateHeight();
        gsap.set(navRef.current, { height: newHeight });

        tlRef.current.kill();
        const newTl = createTimeline();
        if (newTl) {
          newTl.progress(1);
          tlRef.current = newTl;
        }
      } else {
        tlRef.current.kill();
        const newTl = createTimeline();
        if (newTl) {
          tlRef.current = newTl;
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [isExpanded]);

  const toggleMenu = () => {
    const tl = tlRef.current;
    if (!tl) return;
    if (!isExpanded) {
      setIsHamburgerOpen(true);
      setIsExpanded(true);
      tl.play(0);
    } else {
      setIsHamburgerOpen(false);
      tl.eventCallback('onReverseComplete', () => setIsExpanded(false));
      tl.reverse();
    }
  };

  const setCardRef = (i: number) => (el: HTMLDivElement | null) => {
    if (el) cardsRef.current[i] = el;
  };

  return (
    <div className={`card-nav-container ${className}`}>
      <nav 
        ref={navRef} 
        className={`card-nav ${isExpanded ? 'open' : ''} ${isExamDropdownOpen ? 'dropdown-active' : ''}`}
        style={isExamDropdownOpen && !isExpanded ? { overflow: 'visible' } : undefined}
      >
        <div className="card-nav-top">
          {/* Left Corner Logo / Brand */}
          <Link href="/" className="logo-container">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-white font-black text-sm shadow-md shadow-blue-500/20 shrink-0">
              ⚕️
            </div>
            <span className="logo-text font-black tracking-tight">{logoText}</span>
          </Link>

          {/* Right Header Actions */}
          <div className="card-nav-actions">
            {/* Daylight / Night Mode Toggle Slot */}
            {themeToggleSlot}

            {/* Explore Platform Hamburger Button */}
            <div
              className={`hamburger-menu ${isHamburgerOpen ? 'open' : ''}`}
              onClick={toggleMenu}
              onKeyDown={(e: React.KeyboardEvent<HTMLDivElement>) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  toggleMenu();
                }
              }}
              role="button"
              aria-label={isExpanded ? 'Close Platform Explorer' : 'Explore Platform'}
              aria-expanded={isExpanded}
              tabIndex={0}
              title="Explore Platform"
            >
              <div className="hamburger-line" />
              <div className="hamburger-line" />
            </div>

            {/* Select Exam Dropdown Button */}
            <div className="relative" ref={examDropdownRef}>
              <button
                type="button"
                onClick={() => setIsExamDropdownOpen((prev) => !prev)}
                aria-expanded={isExamDropdownOpen}
                aria-haspopup="true"
                className="inline-flex items-center gap-1.5 rounded-full border border-blue-500/40 bg-blue-500/5 px-4 py-2 text-xs font-bold text-slate-900 transition-all duration-300 hover:bg-blue-500/15 focus:outline-hidden focus:ring-2 focus:ring-blue-500/40 dark:bg-blue-500/10 dark:text-slate-100 dark:hover:bg-blue-500/25 cursor-pointer shadow-xs"
              >
                <span>Select Exam</span>
                <ChevronDown className={`h-3.5 w-3.5 text-blue-500 transition-transform duration-300 ${isExamDropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              {/* Glassmorphic Dropdown Menu */}
              {isExamDropdownOpen && (
                <div 
                  className="exam-dropdown-menu"
                  role="menu"
                  aria-orientation="vertical"
                >
                  <div className="px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-wider text-muted-foreground border-b border-border/40 mb-1">
                    Available Exam Microsites
                  </div>
                  {examOptions.map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => handleExamSelect(opt.href)}
                      className="group flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-xs font-bold text-foreground transition-all border-l-4 border-transparent hover:border-primary hover:bg-muted/70 dark:hover:bg-slate-800/80 text-left cursor-pointer"
                      role="menuitem"
                    >
                      <span className="text-base leading-none">{opt.icon}</span>
                      <span className="flex-1 group-hover:text-primary transition-colors">{opt.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Auth Actions */}
            {isAuthenticated ? (
              <Link href="/dashboard" className="card-nav-cta-button">
                Dashboard <ChevronRight className="w-4 h-4" />
              </Link>
            ) : (
              <>
                <Link href="/login" className="card-nav-login-button">
                  Log in
                </Link>
                <Link href="/register" className="card-nav-cta-button">
                  Start Free <Sparkles className="w-3.5 h-3.5" />
                </Link>
              </>
            )}
          </div>
        </div>

        {/* Expandable Nav Cards Content */}
        <div className="card-nav-content" aria-hidden={!isExpanded}>
          {(items || []).slice(0, 3).map((item, idx) => (
            <div
              key={`${item.label}-${idx}`}
              className="nav-card shadow-lg"
              ref={setCardRef(idx)}
              style={{ backgroundColor: item.bgColor, color: item.textColor }}
            >
              <div className="nav-card-label flex items-center justify-between">
                <span>{item.label}</span>
                <span className="text-xs font-mono opacity-60">0{idx + 1}</span>
              </div>
              <div className="nav-card-links">
                {item.links?.map((lnk, i) => (
                  <Link key={`${lnk.label}-${i}`} className="nav-card-link" href={lnk.href} aria-label={lnk.ariaLabel}>
                    <ArrowUpRight className="nav-card-link-icon shrink-0" aria-hidden="true" />
                    <span className="truncate">{lnk.label}</span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </nav>
    </div>
  );
};

export default CardNav;
