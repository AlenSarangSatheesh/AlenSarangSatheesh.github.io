/* ===================================
   Cybersecurity Portfolio - JavaScript
   =================================== */

// ===================================
// Typing Animation
// ===================================
const typingTexts = [
    'whoami | Penetration Tester',
    'nmap -sV target.com',
    'sqlmap -u "http://target.com/?id=1"',
    'burpsuite --proxy-mode',
    'python3 exploit.py --target web.app',
];

let textIndex = 0;
let charIndex = 0;
let isDeleting = false;
const typingElement = document.getElementById('typing-text');

function typeEffect() {
    if (!typingElement) return;
    
    const currentText = typingTexts[textIndex];
    
    if (isDeleting) {
        typingElement.textContent = currentText.substring(0, charIndex - 1);
        charIndex--;
    } else {
        typingElement.textContent = currentText.substring(0, charIndex + 1);
        charIndex++;
    }
    
    let typeSpeed = isDeleting ? 50 : 100;
    
    if (!isDeleting && charIndex === currentText.length) {
        typeSpeed = 2000; // Pause at end
        isDeleting = true;
    } else if (isDeleting && charIndex === 0) {
        isDeleting = false;
        textIndex = (textIndex + 1) % typingTexts.length;
        typeSpeed = 500; // Pause before next text
    }
    
    setTimeout(typeEffect, typeSpeed);
}

// Start typing effect when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(typeEffect, 1000);
});

// ===================================
// Mobile Menu Toggle
// ===================================
function toggleMenu() {
    const hamburgerIcon = document.querySelector('.hamburger-icon');
    const menuLinks = document.querySelector('.menu-links');
    
    if (hamburgerIcon && menuLinks) {
        hamburgerIcon.classList.toggle('open');
        menuLinks.classList.toggle('open');
    }
}

// Close menu when clicking outside
document.addEventListener('click', (e) => {
    const hamburgerMenu = document.querySelector('.hamburger-menu');
    const menuLinks = document.querySelector('.menu-links');
    
    if (hamburgerMenu && menuLinks && !hamburgerMenu.contains(e.target)) {
        menuLinks.classList.remove('open');
        document.querySelector('.hamburger-icon')?.classList.remove('open');
    }
});

// ===================================
// Smooth Scroll for Navigation Links
// ===================================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        
        if (target) {
            const navHeight = document.querySelector('nav')?.offsetHeight || 0;
            const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navHeight;
            
            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });
        }
    });
});

// ===================================
// Scroll Reveal Animation
// ===================================
const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('fade-in');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe elements for scroll animation
document.addEventListener('DOMContentLoaded', () => {
    const animatedElements = document.querySelectorAll(
        '.skill-category, .project-card, .stat-card, .contact-method, .about-content'
    );
    
    animatedElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        observer.observe(el);
    });
});

// ===================================
// Navigation Background on Scroll
// ===================================
let lastScroll = 0;

window.addEventListener('scroll', () => {
    const nav = document.querySelector('nav');
    const currentScroll = window.pageYOffset;
    
    if (nav) {
        if (currentScroll > 50) {
            nav.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.3)';
        } else {
            nav.style.boxShadow = 'none';
        }
    }
    
    lastScroll = currentScroll;
});

// ===================================
// Matrix Rain Background Effect (Optional)
// ===================================
function initMatrixRain() {
    const canvas = document.createElement('canvas');
    canvas.id = 'matrix-canvas';
    canvas.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: -1;
        opacity: 0.03;
    `;
    
    const matrixBg = document.getElementById('matrix-bg');
    if (matrixBg) {
        matrixBg.appendChild(canvas);
        
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        
        const chars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';
        const fontSize = 14;
        const columns = canvas.width / fontSize;
        const drops = Array(Math.floor(columns)).fill(1);
        
        function drawMatrix() {
            ctx.fillStyle = 'rgba(10, 10, 15, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            ctx.fillStyle = '#00ff41';
            ctx.font = `${fontSize}px monospace`;
            
            for (let i = 0; i < drops.length; i++) {
                const text = chars[Math.floor(Math.random() * chars.length)];
                ctx.fillText(text, i * fontSize, drops[i] * fontSize);
                
                if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
        }
        
        // Only enable matrix rain on larger screens
        if (window.innerWidth > 768) {
            setInterval(drawMatrix, 50);
        }
        
        // Handle resize
        window.addEventListener('resize', () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });
    }
}

// Initialize matrix effect (uncomment to enable)
// document.addEventListener('DOMContentLoaded', initMatrixRain);

// ===================================
// Console Easter Egg
// ===================================
console.log('%c🔒 Alen Sarang Satheesh - Penetration Tester', 'font-size: 20px; font-weight: bold; color: #00ff41;');
console.log('%cLooking to hire or collaborate? Contact me at alensarangsatheesh@gmail.com', 'font-size: 14px; color: #00d9ff;');
console.log('%c⚠️ This website is secured. Nice try! 😉', 'font-size: 12px; color: #ff5f56;');
