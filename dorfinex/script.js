function init() {
    const hasGSAP = typeof gsap !== 'undefined';
    const hasScrollTrigger = typeof ScrollTrigger !== 'undefined';
    const hasScrollToPlugin = typeof ScrollToPlugin !== 'undefined';

    if (hasGSAP && hasScrollTrigger) {
        if (hasScrollToPlugin) {
            gsap.registerPlugin(ScrollTrigger, ScrollToPlugin);
        } else {
            gsap.registerPlugin(ScrollTrigger);
        }
    }

    // Loader animation with no-JS-lib fallback.
    const hideLoader = () => {
        const loader = document.getElementById('loader');
        if (!loader || loader.classList.contains('hidden')) return;

        if (hasGSAP) {
            gsap.to(loader, {
                opacity: 0,
                duration: 0.5,
                delay: 0.14,
                onComplete: () => loader.classList.add('hidden')
            });
            return;
        }

        loader.classList.add('hidden');
    };

    if (document.readyState === 'complete') {
        hideLoader();
    } else {
        window.addEventListener('load', hideLoader, { once: true });
    }
    setTimeout(hideLoader, 3000);

    // Keep copyright year current without manual edits.
    const year = new Date().getFullYear();
    document.querySelectorAll('.js-current-year').forEach((el) => {
        el.textContent = String(year);
    });

    // Navigation: scrolled state
    const nav = document.getElementById('nav');
    if (nav) {
        const onScroll = () => {
            const currentScroll = window.pageYOffset;
            nav.classList.toggle('scrolled', currentScroll > 40);
        };
        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
    }

    // Navigation: active link (multi-page)
    const bodyPage = document.body?.dataset?.page;
    const pathPage = (window.location.pathname.split('/').pop() || 'index.html').toLowerCase();
    const currentPage = bodyPage || pathPage.replace('.html', '');

    document.querySelectorAll('.nav-link[data-page]').forEach((link) => {
        const isActive = link.getAttribute('data-page') === currentPage;
        link.classList.toggle('active', isActive);
        if (isActive) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
    });

    // Mobile navigation toggle with basic a11y state.
    const navToggle = document.getElementById('navToggle');
    const navLinks = document.querySelector('.nav-links');

    if (navToggle && navLinks) {
        if (!navLinks.id) {
            navLinks.id = 'primary-navigation';
        }

        navToggle.setAttribute('aria-controls', navLinks.id);
        navToggle.setAttribute('aria-expanded', 'false');

        const setNavOpen = (isOpen) => {
            navLinks.classList.toggle('active', isOpen);
            navToggle.setAttribute('aria-expanded', String(isOpen));
        };

        navToggle.addEventListener('click', () => {
            const isOpen = navLinks.classList.contains('active');
            setNavOpen(!isOpen);
        });

        document.querySelectorAll('.nav-link').forEach((link) => {
            link.addEventListener('click', () => setNavOpen(false));
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                setNavOpen(false);
            }
        });

        document.addEventListener('click', (event) => {
            const clickTarget = event.target;
            if (!(clickTarget instanceof Element)) return;
            if (nav.contains(clickTarget)) return;
            setNavOpen(false);
        });
    }

    // Smooth scroll for same-page anchors.
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener('click', function onAnchorClick(event) {
            const targetId = this.getAttribute('href');
            const target = targetId ? document.querySelector(targetId) : null;
            if (!target) return;

            event.preventDefault();
            if (hasGSAP && hasScrollToPlugin) {
                gsap.to(window, {
                    duration: 0.9,
                    scrollTo: { y: target, offsetY: 90 },
                    ease: 'power2.inOut'
                });
            } else {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // FAQ accordion
    document.querySelectorAll('.faq-item').forEach((item, index) => {
        const trigger = item.querySelector('.faq-trigger');
        const panel = item.querySelector('.faq-panel');
        if (!trigger || !panel) return;

        const panelId = panel.id || `faq-panel-${index + 1}`;
        const triggerId = trigger.id || `faq-trigger-${index + 1}`;

        panel.id = panelId;
        trigger.id = triggerId;
        trigger.setAttribute('aria-controls', panelId);
        trigger.setAttribute('aria-expanded', 'false');
        panel.setAttribute('role', 'region');
        panel.setAttribute('aria-labelledby', triggerId);
        panel.style.maxHeight = '0px';

        trigger.addEventListener('click', () => {
            const isOpen = item.classList.toggle('open');
            trigger.setAttribute('aria-expanded', String(isOpen));
            panel.style.maxHeight = isOpen ? `${panel.scrollHeight}px` : '0px';
        });
    });

    // Contact forms: validate and submit to endpoint (Formspree/other).
    document.querySelectorAll('form.js-contact-form').forEach((form) => {
        const submitButton = form.querySelector('button[type="submit"]');
        const status = form.querySelector('#formStatus') || form.querySelector('.form-status');

        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            const name = form.querySelector('[name="name"]');
            const email = form.querySelector('[name="email"]');
            const message = form.querySelector('[name="message"]');
            const endpoint = form.dataset.formEndpoint || form.getAttribute('action') || '';

            const emailOk = Boolean(email?.value && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim()));
            const ok = Boolean(name?.value.trim() && emailOk && message?.value.trim());

            if (!ok) {
                if (status) {
                    status.textContent = 'Please fill in your name, a valid email, and your message.';
                    status.classList.add('error');
                    status.classList.remove('success');
                }
                return;
            }

            if (!endpoint || endpoint === '#') {
                if (status) {
                    status.textContent = 'Form endpoint is not configured yet. Add your provider endpoint in the form action.';
                    status.classList.add('error');
                    status.classList.remove('success');
                }
                return;
            }

            if (submitButton) submitButton.disabled = true;
            if (status) {
                status.textContent = 'Sending...';
                status.classList.remove('error', 'success');
            }

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: { Accept: 'application/json' }
                });

                if (!response.ok) {
                    throw new Error(`Form submit failed with status ${response.status}`);
                }

                if (status) {
                    status.textContent = 'Thanks. Your message has been sent.';
                    status.classList.remove('error');
                    status.classList.add('success');
                }
                form.reset();
            } catch (error) {
                if (status) {
                    status.textContent = 'Message could not be sent right now. Please try again in a few minutes.';
                    status.classList.add('error');
                    status.classList.remove('success');
                }
                console.error(error);
            } finally {
                if (submitButton) submitButton.disabled = false;
            }
        });
    });

    if (!hasGSAP) return;

    // Hero / page header animations (only if present)
    const hasHero = document.querySelector('.hero');
    if (hasHero) {
        const heroTimeline = gsap.timeline({ delay: 1.0 });
        heroTimeline
            .from('.hero-badge', { opacity: 0, y: 18, duration: 0.7, ease: 'power2.out' })
            .from('.hero-title .title-line', { opacity: 0, y: 18, duration: 0.75, stagger: 0.08, ease: 'power2.out' }, '-=0.35')
            .from('.hero-subtitle', { opacity: 0, y: 14, duration: 0.6, ease: 'power2.out' }, '-=0.35')
            .from('.hero-actions .btn', { opacity: 0, y: 12, duration: 0.5, stagger: 0.08, ease: 'power2.out' }, '-=0.25')
            .from('.scroll-indicator', { opacity: 0, y: 10, duration: 0.6, ease: 'power2.out' }, '-=0.35');
    }

    const pageHero = document.querySelector('.page-hero');
    if (pageHero) {
        gsap.from(['.page-kicker', '.page-title', '.page-subtitle'], {
            opacity: 0,
            y: 14,
            duration: 0.7,
            stagger: 0.12,
            ease: 'power2.out',
            delay: 0.9
        });
    }

    // Animate gradient orbs.
    gsap.to('.orb-1', { x: 60, y: -40, duration: 24, repeat: -1, yoyo: true, ease: 'sine.inOut' });
    gsap.to('.orb-2', { x: -50, y: 40, duration: 28, repeat: -1, yoyo: true, ease: 'sine.inOut' });
    gsap.to('.orb-3', { x: 35, y: -28, duration: 22, repeat: -1, yoyo: true, ease: 'sine.inOut' });

    // Animate grid overlays with parallax effect.
    const gridOverlays = document.querySelectorAll('.grid-overlay');

    if (gridOverlays.length > 0) {
        document.addEventListener('mousemove', (event) => {
            const mouseX = event.clientX / window.innerWidth;
            const mouseY = event.clientY / window.innerHeight;

            gridOverlays.forEach((grid, index) => {
                const speed = (index + 1) * 0.5;
                const moveX = (mouseX - 0.5) * 20 * speed;
                const moveY = (mouseY - 0.5) * 20 * speed;

                gsap.to(grid, {
                    x: moveX,
                    y: moveY,
                    duration: 1,
                    ease: 'power1.out'
                });
            });
        });

        if (hasScrollTrigger) {
            gridOverlays.forEach((grid, index) => {
                gsap.to(grid, {
                    y: (index + 1) * 50,
                    ease: 'none',
                    scrollTrigger: {
                        trigger: '.hero',
                        start: 'top top',
                        end: 'bottom top',
                        scrub: true
                    }
                });
            });
        }
    }

    if (hasScrollTrigger) {
        // Scroll reveal animations (shared)
        gsap.utils.toArray('.reveal').forEach((el) => {
            gsap.from(el, {
                opacity: 0,
                y: 28,
                duration: 0.75,
                ease: 'power2.out',
                scrollTrigger: { trigger: el, start: 'top 85%', toggleActions: 'play none none none' }
            });
        });

        // Card animations (services/insights/value cards)
        gsap.utils.toArray('.card').forEach((card) => {
            gsap.from(card, {
                opacity: 0,
                y: 26,
                duration: 0.7,
                ease: 'power2.out',
                scrollTrigger: { trigger: card, start: 'top 88%', toggleActions: 'play none none none' }
            });
        });

        // Section header animation
        gsap.utils.toArray('.section-header').forEach((header) => {
            gsap.from(header.children, {
                opacity: 0,
                y: 18,
                duration: 0.7,
                stagger: 0.12,
                ease: 'power2.out',
                scrollTrigger: { trigger: header, start: 'top 85%', toggleActions: 'play none none none' }
            });
        });

        // CTA animation
        const ctaContent = document.querySelector('.cta-content');
        if (ctaContent) {
            gsap.from(ctaContent, {
                opacity: 0,
                y: 22,
                duration: 0.8,
                ease: 'power2.out',
                scrollTrigger: { trigger: ctaContent, start: 'top 85%', toggleActions: 'play none none none' }
            });
        }

        // Parallax effect on hero background
        const heroBackground = document.querySelector('.hero-background');
        if (heroBackground && document.querySelector('.hero')) {
            gsap.to(heroBackground, {
                y: '18%',
                ease: 'none',
                scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: true }
            });
        }
    }

    // Lightweight hover for buttons.
    document.querySelectorAll('.btn').forEach((btn) => {
        btn.addEventListener('mouseenter', function onMouseEnter() {
            gsap.to(this, { y: -2, duration: 0.2, ease: 'power2.out' });
        });
        btn.addEventListener('mouseleave', function onMouseLeave() {
            gsap.to(this, { y: 0, duration: 0.2, ease: 'power2.out' });
        });
    });

    // Performance: reduce motion for users who prefer it.
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        gsap.globalTimeline.timeScale(0.5);
    }
}

// Start initialization
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
