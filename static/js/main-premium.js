/**
 * Premium SaaS Agriculture Dashboard
 * Advanced Animations & Interactivity
 */

// ============================================
// Document Ready
// ============================================

document.addEventListener("DOMContentLoaded", function () {
  initializeNavbar();
  initializeScrollAnimations();
  initializeIntersectionObserver();
  initializeInteractiveElements();
  initializeCounterAnimation();
  loadDynamicMetrics();
});

// ============================================
// NAVBAR FUNCTIONALITY
// ============================================

function initializeNavbar() {
  const navbar = document.querySelector(".navbar-wrapper");
  const navToggle = document.querySelector(".navbar-toggle");
  const navMenu = document.querySelector(".navbar-menu");
  let lastScrollTop = 0;

  // Navbar scroll effect
  window.addEventListener("scroll", function () {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

    if (scrollTop > 50) {
      navbar.classList.add("scrolled");
    } else {
      navbar.classList.remove("scrolled");
    }

    lastScrollTop = scrollTop;
  });

  // Mobile menu toggle
  if (navToggle) {
    navToggle.addEventListener("click", function () {
      navMenu.classList.toggle("active");
      navToggle.classList.toggle("active");
    });
  }

  // Close menu on link click
  const navLinks = document.querySelectorAll(".nav-link");
  navLinks.forEach((link) => {
    link.addEventListener("click", function () {
      navMenu.classList.remove("active");
      if (navToggle) navToggle.classList.remove("active");

      // Update active state
      navLinks.forEach((l) => l.classList.remove("active"));
      this.classList.add("active");
    });
  });

  // Set active link based on current page
  updateActiveNavLink();
}

function updateActiveNavLink() {
  const currentPage = window.location.pathname;
  const navLinks = document.querySelectorAll(".nav-link");

  navLinks.forEach((link) => {
    if (
      link.getAttribute("href") === currentPage ||
      (currentPage === "/" && link.getAttribute("href").includes("index"))
    ) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });
}

// ============================================
// SCROLL ANIMATIONS
// ============================================

function initializeScrollAnimations() {
  const observerOptions = {
    threshold: 0.1,
    rootMargin: "0px 0px -100px 0px",
  };

  const observer = new IntersectionObserver(function (entries) {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  // Observe all animated elements
  document
    .querySelectorAll(
      ".fade-in-up, .fade-in-down, .fade-in-left, .fade-in-right",
    )
    .forEach((el) => {
      observer.observe(el);
    });
}

// ============================================
// INTERSECTION OBSERVER FOR ADVANCED EFFECTS
// ============================================

function initializeIntersectionObserver() {
  const sections = document.querySelectorAll(
    ".metrics-section, .modules-section, .features-section, .cta-section",
  );

  const sectionObserver = new IntersectionObserver(
    function (entries) {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
        }
      });
    },
    {
      threshold: 0.1,
    },
  );

  sections.forEach((section) => sectionObserver.observe(section));
}

// ============================================
// INTERACTIVE ELEMENTS
// ============================================

function initializeInteractiveElements() {
  // Button ripple effect
  const buttons = document.querySelectorAll(".btn");
  buttons.forEach((button) => {
    button.addEventListener("click", function (e) {
      const ripple = document.createElement("span");
      const rect = this.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const x = e.clientX - rect.left - size / 2;
      const y = e.clientY - rect.top - size / 2;

      ripple.style.width = size + "px";
      ripple.style.height = size + "px";
      ripple.style.left = x + "px";
      ripple.style.top = y + "px";

      this.appendChild(ripple);

      setTimeout(() => ripple.remove(), 600);
    });
  });

  // Card hover effects
  const cards = document.querySelectorAll(
    ".module-premium-card, .metric-card, .feature-card, .flow-step",
  );
  cards.forEach((card) => {
    card.addEventListener("mouseenter", function () {
      this.style.transition = "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)";
    });
  });
}

// ============================================
// COUNTER ANIMATIONS
// ============================================

function initializeCounterAnimation() {
  const metricCards = document.querySelectorAll(".metric-card");
  let animated = false;

  const cardObserver = new IntersectionObserver(
    function (entries) {
      entries.forEach((entry) => {
        if (entry.isIntersecting && !animated) {
          animated = true;
          animateMetrics();
          cardObserver.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.5 },
  );

  if (metricCards.length > 0) {
    cardObserver.observe(metricCards[0]);
  }
}

function animateMetrics() {
  const metrics = [
    { target: 5, duration: 2000 },
    { target: 1000000, duration: 2000 },
    { target: 94, duration: 2000 },
    { target: 32, duration: 2000 },
  ];

  const metricCards = document.querySelectorAll(".metric-card");

  metricCards.forEach((card, index) => {
    const h3 = card.querySelector(".metric-content h3");
    if (h3 && metrics[index]) {
      animateCounter(h3, metrics[index].target, metrics[index].duration);
    }
  });
}

function animateCounter(element, target, duration) {
  let current = 0;
  const increment = target / (duration / 16); // 60fps
  const originalText = element.textContent;

  if (originalText.includes("M")) {
    target = 1000000;
  } else if (originalText.includes("K")) {
    target = 1000;
  }

  const timer = setInterval(() => {
    current += increment;
    if (current >= target) {
      current = target;
      clearInterval(timer);
      updateCounterDisplay(element, current, originalText);
    } else {
      updateCounterDisplay(element, current, originalText);
    }
  }, 16);
}

function updateCounterDisplay(element, value, originalText) {
  if (originalText.includes("M")) {
    element.textContent = Math.floor(value / 1000000) + "M+";
  } else if (originalText.includes("K")) {
    element.textContent = Math.floor(value / 1000) + "K+";
  } else if (originalText.includes("%")) {
    element.textContent = Math.floor(value) + "%";
  } else {
    element.textContent = Math.floor(value);
  }
}

// ============================================
// LOAD DYNAMIC METRICS
// ============================================

function loadDynamicMetrics() {
  fetch("/api/metrics")
    .then((response) => response.json())
    .then((data) => {
      if (data.ok && data.metrics) {
        updateMetricsDisplay(data.metrics);
      }
    })
    .catch((error) => {
      console.log("Metrics API not available, using default values");
    });
}

function updateMetricsDisplay(metrics) {
  // Update ML Models
  const modelsEl = document.getElementById("metric-models");
  if (modelsEl) {
    modelsEl.textContent = metrics.ml_models;
  }

  // Update Data Points
  const datapointsEl = document.getElementById("metric-datapoints");
  if (datapointsEl) {
    const dataPoints = metrics.data_points;
    if (dataPoints >= 1000000) {
      datapointsEl.textContent = (dataPoints / 1000000).toFixed(1) + "M+";
    } else if (dataPoints >= 1000) {
      datapointsEl.textContent = (dataPoints / 1000).toFixed(1) + "K+";
    } else {
      datapointsEl.textContent = dataPoints;
    }
  }

  // Update Accuracy
  const accuracyEl = document.getElementById("metric-accuracy");
  if (accuracyEl) {
    accuracyEl.textContent = metrics.accuracy + "%";
  }

  // Update States
  const statesEl = document.getElementById("metric-states");
  if (statesEl) {
    statesEl.textContent = metrics.states_covered;
  }

  console.log("✅ Dynamic metrics loaded:", metrics);
}

// ============================================
// SMOOTH SCROLL FOR ANCHOR LINKS
// ============================================

document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
  anchor.addEventListener("click", function (e) {
    const href = this.getAttribute("href");
    if (href === "#") return;

    e.preventDefault();
    const target = document.querySelector(href);

    if (target) {
      target.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  });
});

// ============================================
// PARALLAX EFFECT FOR HERO
// ============================================

function initializeParallaxEffect() {
  const heroSection = document.querySelector(".hero-section");
  const floatingShapes = document.querySelectorAll(".floating-shape");

  if (heroSection) {
    window.addEventListener("scroll", () => {
      const scrollY = window.pageYOffset;
      floatingShapes.forEach((shape, index) => {
        const speed = 0.5 + index * 0.1;
        shape.style.transform = `translateY(${scrollY * speed}px)`;
      });
    });
  }
}

// ============================================
// ENHANCE DASHBOARD PREVIEW
// ============================================

function initializeDashboardPreview() {
  const dashboardPreview = document.querySelector(".dashboard-preview");

  if (dashboardPreview) {
    dashboardPreview.addEventListener("mouseenter", function () {
      this.style.transform = "rotateY(-2deg) rotateX(2deg) scale(1.02)";
    });

    dashboardPreview.addEventListener("mouseleave", function () {
      this.style.transform = "rotateY(-5deg) rotateX(5deg) scale(1)";
    });
  }
}

// ============================================
// INITIALIZE ALL FEATURES
// ============================================

document.addEventListener("DOMContentLoaded", function () {
  initializeParallaxEffect();
  initializeDashboardPreview();

  // Add fade-in class to elements not in viewport
  const fadeElements = document.querySelectorAll('[class*="fade-in"]');
  fadeElements.forEach((el) => {
    if (!isInViewport(el)) {
      el.style.opacity = "0";
    }
  });
});

function isInViewport(element) {
  const rect = element.getBoundingClientRect();
  return (
    rect.top >= 0 &&
    rect.left >= 0 &&
    rect.bottom <=
      (window.innerHeight || document.documentElement.clientHeight) &&
    rect.right <= (window.innerWidth || document.documentElement.clientWidth)
  );
}

// ============================================
// RESPONSIVE UTILITIES
// ============================================

function handleResponsive() {
  const width = window.innerWidth;

  if (width <= 768) {
    document.body.classList.add("mobile");
    document.body.classList.remove("desktop");
  } else {
    document.body.classList.remove("mobile");
    document.body.classList.add("desktop");
  }
}

window.addEventListener("resize", handleResponsive);
window.addEventListener("load", handleResponsive);
handleResponsive();

// ============================================
// PERFORMANCE OPTIMIZATION
// ============================================

// Lazy load images
if ("IntersectionObserver" in window) {
  const imageObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const img = entry.target;
        img.src = img.dataset.src;
        img.classList.add("loaded");
        observer.unobserve(img);
      }
    });
  });

  document
    .querySelectorAll("img[data-src]")
    .forEach((img) => imageObserver.observe(img));
}

// ============================================
// ANALYTICS & TRACKING (Optional)
// ============================================

function trackUserInteraction(action, category, label) {
  if (typeof gtag !== "undefined") {
    gtag("event", action, {
      event_category: category,
      event_label: label,
    });
  }
}

// Track CTA clicks
document.querySelectorAll(".btn-cta, .navbar-cta").forEach((button) => {
  button.addEventListener("click", function () {
    trackUserInteraction("cta_click", "engagement", this.textContent.trim());
  });
});

// ============================================
// LOG INITIALIZATION
// ============================================

console.log(
  "🌾 Smart India Agri Intelligence System - Premium Dashboard Initialized",
);
