function splitTabsForLayout(tabs, availableWidth, moreWidth) {
    const orderedTabs = Array.isArray(tabs) ? [...tabs] : [];
    const totalWidth = orderedTabs.reduce((sum, tab) => sum + (tab.width || 0), 0);

    if (totalWidth <= availableWidth) {
        return { visible: orderedTabs, overflow: [] };
    }

    const reservedWidth = Math.max(0, availableWidth - moreWidth);
    const visible = [];
    const overflow = [];
    let usedWidth = 0;

    orderedTabs.forEach(tab => {
        const tabWidth = tab.width || 0;
        if (usedWidth + tabWidth <= reservedWidth || visible.length === 0) {
            visible.push(tab);
            usedWidth += tabWidth;
            return;
        }
        overflow.push(tab);
    });

    return { visible, overflow };
}

function hasActiveOverflowTab(overflowTabs, activeTab) {
    return (overflowTabs || []).some(tab => tab.id === activeTab);
}

function getOverlayMode(viewportWidth) {
    return viewportWidth < 768 ? 'sheet' : 'modal';
}

const api = {
    splitTabsForLayout,
    hasActiveOverflowTab,
    getOverlayMode,
};

if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
}

if (typeof window !== 'undefined') {
    window.NexusDashboardCore = api;
}
