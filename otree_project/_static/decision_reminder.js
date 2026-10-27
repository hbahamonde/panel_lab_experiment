/* A soft decision guide. No answer is chosen and no form is submitted here. */
(function () {
    function initializeReminder() {
        if (typeof js_vars === 'undefined' || !js_vars.decision_reminder) return;
        if (document.querySelector('.decision-reminder')) return;

        const form = document.querySelector('#form') || document.querySelector('form');
        if (!form) return;
        const settings = js_vars.decision_reminder;
        const remainingAtLoad = Math.max(0, Number(settings.remaining_seconds) || 0);
        const startedAt = performance.now();

        const panel = document.createElement('aside');
        panel.className = 'decision-reminder';
        panel.setAttribute('aria-label', 'Muistutus päätöksestä');
        panel.innerHTML =
            '<div class="decision-reminder-heading">' +
            '<strong class="decision-reminder-title">Päätösmuistutus</strong>' +
            '<span class="decision-reminder-clock" aria-hidden="true"></span></div>' +
            '<p>Valitse vastauksesi ja lähetä se napsauttamalla <strong>Seuraava</strong>.</p>' +
            '<small>Ajastin on vain ohjeellinen. Sivu pysyy auki.</small>' +
            '<span class="decision-reminder-status visually-hidden" role="status" aria-live="polite"></span>';
        form.prepend(panel);

        const clock = panel.querySelector('.decision-reminder-clock');
        const title = panel.querySelector('.decision-reminder-title');
        const status = panel.querySelector('.decision-reminder-status');
        let reminded = false;
        let interval;

        function updateReminder() {
            const remaining = Math.max(
                0, Math.ceil(remainingAtLoad - (performance.now() - startedAt) / 1000)
            );
            clock.textContent = Math.floor(remaining / 60) + ':' +
                String(remaining % 60).padStart(2, '0');
            if (remaining > 0 || reminded) return;
            reminded = true;
            panel.classList.add('decision-reminder-due');
            title.textContent = 'Viimeistele päätöksesi';
            status.textContent = 'Valitse vastauksesi ja napsauta Seuraava. Sivu pysyy auki.';
            const nextButton = form.querySelector('.otree-btn-next');
            if (nextButton) nextButton.classList.add('decision-next-reminder');
            if (interval) clearInterval(interval);
        }

        updateReminder();
        if (!reminded) interval = setInterval(updateReminder, 1000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeReminder);
    } else {
        initializeReminder();
    }
})();
