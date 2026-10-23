/* One native disclosure is shared by desktop and mobile navigation. */
(() => {
    const menu = document.querySelector('.workspace-menu');
    if (!menu) return;
    const narrow = window.matchMedia('(max-width: 48rem)');
    const syncMenu = () => { menu.open = !narrow.matches; };
    syncMenu();
    narrow.addEventListener('change', syncMenu);
    menu.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && narrow.matches && menu.open) {
            menu.open = false;
            menu.querySelector('summary').focus();
        }
    });
})();
