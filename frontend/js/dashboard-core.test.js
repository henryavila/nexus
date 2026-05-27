const test = require('node:test');
const assert = require('node:assert/strict');

const {
    splitTabsForLayout,
    getOverlayMode,
    hasActiveOverflowTab,
} = require('./dashboard-core.js');

test('splitTabsForLayout keeps original order and moves overflow to Mais', () => {
    const tabs = [
        { id: 'ideas', label: '1 Ideias', width: 92 },
        { id: 'projects', label: '2 Projetos', width: 108 },
        { id: 'apps', label: '3 Apps', width: 82 },
        { id: 'skills', label: '4 Skills', width: 88 },
    ];

    const result = splitTabsForLayout(tabs, 310, 84);

    assert.deepEqual(result.visible.map(tab => tab.id), ['ideas', 'projects']);
    assert.deepEqual(result.overflow.map(tab => tab.id), ['apps', 'skills']);
});

test('splitTabsForLayout returns all tabs visible when there is enough space', () => {
    const tabs = [
        { id: 'ideas', label: '1 Ideias', width: 92 },
        { id: 'projects', label: '2 Projetos', width: 108 },
    ];

    const result = splitTabsForLayout(tabs, 400, 84);

    assert.equal(result.overflow.length, 0);
    assert.deepEqual(result.visible.map(tab => tab.id), ['ideas', 'projects']);
});

test('hasActiveOverflowTab reports when active tab is hidden under Mais', () => {
    const overflow = [{ id: 'skills' }, { id: 'codex' }];

    assert.equal(hasActiveOverflowTab(overflow, 'skills'), true);
    assert.equal(hasActiveOverflowTab(overflow, 'ideas'), false);
});

test('getOverlayMode is sheet on mobile and modal on desktop', () => {
    assert.equal(getOverlayMode(390), 'sheet');
    assert.equal(getOverlayMode(1200), 'modal');
});
