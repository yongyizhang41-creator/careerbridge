(() => {
    const board = document.querySelector('[data-pipeline]');
    if (!board) return;
    const feedback = document.getElementById('pipeline-feedback');
    let draggedCard = null;
    let busy = false;
    function refreshCounts() {
        board.querySelectorAll('[data-stage]').forEach(column => {
            const count = column.querySelectorAll('[data-application]').length;
            column.querySelector('[data-stage-count]').textContent = count;
            column.querySelector('.pipeline__empty').hidden = count !== 0;
        });
    }
    async function moveCard(card, stage) {
        if (busy) return;
        const form = card.querySelector('[data-move-form]');
        const data = new FormData(form);
        data.set('status', stage);
        const previous = form.elements.expected_status.value;
        if (previous === stage) return;
        busy = true;
        board.setAttribute('aria-busy', 'true');
        board.querySelectorAll('select, button').forEach(control => { control.disabled = true; });
        feedback.textContent = 'Saving stage...';
        try {
            const response = await fetch(form.action, {
                method: 'POST', body: data, credentials: 'same-origin',
                headers: {'Accept': 'application/json'},
            });
            if (response.redirected) throw new Error('Your session may have expired. Reload the page and sign in again.');
            if (!response.headers.get('Content-Type')?.includes('application/json')) {
                throw new Error('Unable to save the stage. Reload the page and sign in if needed.');
            }
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Unable to save the stage. Reload and try again.');
            const column = Array.from(board.querySelectorAll('[data-stage]')).find(item => item.dataset.stage === result.status);
            column.querySelector('.pipeline__cards').append(card);
            form.elements.expected_status.value = result.status;
            form.elements.status.value = result.status;
            refreshCounts();
            feedback.textContent = 'Application moved to ' + result.label + '.';
        } catch (error) {
            form.elements.status.value = previous;
            feedback.textContent = error instanceof TypeError || error instanceof SyntaxError
                ? 'Connection interrupted. Reload to check the saved stage and try again.'
                : error.message;
        } finally {
            busy = false;
            board.removeAttribute('aria-busy');
            board.querySelectorAll('select, button').forEach(control => { control.disabled = false; });
        }
    }
    board.querySelectorAll('[data-application]').forEach(card => {
        card.draggable = true;
        card.addEventListener('dragstart', event => {
            if (busy || event.target.closest('input, select, button')) { event.preventDefault(); return; }
            draggedCard = card;
            event.dataTransfer.setData('text/plain', card.dataset.application);
            event.dataTransfer.effectAllowed = 'move';
            card.classList.add('pipeline__card--dragging');
        });
        card.addEventListener('dragend', () => {
            draggedCard = null;
            card.classList.remove('pipeline__card--dragging');
            board.querySelectorAll('.pipeline__column--over').forEach(column => column.classList.remove('pipeline__column--over'));
        });
        card.querySelector('form').addEventListener('submit', event => {
            event.preventDefault();
            moveCard(card, event.currentTarget.elements.status.value);
        });
    });
    board.querySelectorAll('[data-stage]').forEach(column => {
        column.addEventListener('dragover', event => {
            if (!draggedCard || busy) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = 'move';
            column.classList.add('pipeline__column--over');
        });
        column.addEventListener('dragleave', event => {
            if (!column.contains(event.relatedTarget)) column.classList.remove('pipeline__column--over');
        });
        column.addEventListener('drop', event => {
            event.preventDefault();
            column.classList.remove('pipeline__column--over');
            if (draggedCard) moveCard(draggedCard, column.dataset.stage);
        });
    });
})();
