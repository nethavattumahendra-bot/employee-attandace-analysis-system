/**
 * AttendIQ Enterprise Client-Side Scripts
 * Modals, Dropdowns, Notifications, and Responsive Navigation
 */

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Global window event listeners
window.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal-overlay') || event.target.classList.contains('modal')) {
        event.target.classList.remove('active');
        document.body.style.overflow = '';
    }
});

window.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active, .modal.active').forEach(modal => {
            modal.classList.remove('active');
        });
        document.querySelectorAll('.dropdown-pane.active').forEach(p => p.classList.remove('active'));
        document.body.style.overflow = '';
    }
});

document.addEventListener('DOMContentLoaded', function() {
    // 1. Mobile menu toggle
    const toggleBtn = document.getElementById('menuToggle');
    const sidebar = document.getElementById('appSidebar') || document.querySelector('.sidebar');
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            sidebar.classList.toggle('mobile-open');
        });

        document.addEventListener('click', function(e) {
            if (window.innerWidth <= 768 && sidebar.classList.contains('mobile-open')) {
                if (!sidebar.contains(e.target) && e.target !== toggleBtn) {
                    sidebar.classList.remove('mobile-open');
                }
            }
        });
    }

    // 2. Dropdowns Handling (Notifications & User Profile)
    function setupDropdown(btnId, paneId) {
        const btn = document.getElementById(btnId);
        const pane = document.getElementById(paneId);
        if (btn && pane) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                // Close other open panes
                document.querySelectorAll('.dropdown-pane.active').forEach(p => {
                    if (p !== pane) p.classList.remove('active');
                });
                pane.classList.toggle('active');
            });
        }
    }

    setupDropdown('notifBtn', 'notifPane');
    setupDropdown('userMenuBtn', 'userMenuPane');

    document.addEventListener('click', function(e) {
        if (!e.target.closest('.dropdown-wrapper')) {
            document.querySelectorAll('.dropdown-pane.active').forEach(p => p.classList.remove('active'));
        }
    });

    // 3. Auto-dismiss flash alerts after 6 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            alert.style.transition = 'opacity 0.4s ease';
            alert.style.opacity = '0';
            setTimeout(function() { alert.remove(); }, 400);
        }, 6000);
    });

    // 4. Dark/Light Mode Theme Toggle
    function initThemeToggle() {
        const toggleButtons = document.querySelectorAll('#themeToggleBtn, .theme-toggle-btn');
        if (!toggleButtons.length) return;

        function updateToggleTitle(theme) {
            toggleButtons.forEach(btn => {
                btn.setAttribute('title', theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode');
                btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode');
            });
        }

        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        updateToggleTitle(currentTheme);

        toggleButtons.forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const active = document.documentElement.getAttribute('data-theme') || 'light';
                const nextTheme = active === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', nextTheme);
                try {
                    localStorage.setItem('attendiq_theme', nextTheme);
                } catch(err) {}
                updateToggleTitle(nextTheme);
            });
        });
    }

    initThemeToggle();
});
