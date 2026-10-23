"use strict";

const emailForm = document.getElementById("candidate-email-form");
if (emailForm) {
    emailForm.addEventListener("submit", (event) => {
        if (!emailForm.reportValidity()) return;
        const subject = emailForm.elements.subject.value.trim();
        if (/[\r\n]/.test(subject)) return;
        event.preventDefault();
        const recipient = encodeURIComponent(emailForm.dataset.recipient);
        const body = emailForm.elements.body.value.trim().replace(/\r?\n/g, "\r\n");
        window.location.href = `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    });
}
