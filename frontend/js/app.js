const TAB_REGISTRY = [
    { id: 'ideas', label: 'Ideias', index: 1 },
    { id: 'projects', label: 'Projetos', index: 2 },
    { id: 'apps', label: 'Apps', index: 3 },
    { id: 'skills', label: 'Skills', index: 4 },
    { id: 'environments', label: 'Environments', index: 5 },
    { id: 'codex', label: 'Codex', index: 6 },
];

let activeTab = 'ideas';
let cachedProjects = [];
let cachedApps = [];
let cachedSkills = {};
let cachedEnvironments = [];
let cachedIdeas = [];
let cachedCodex = [];
let cachedLastScan = null;
let cachedCurrentEnvironment = null;
let navState = { visible: TAB_REGISTRY, overflow: [] };
let resizeScheduled = false;

const dom = {};

async function loadData() {
    const response = await fetch('data.json');
    if (!response.ok) {
        throw new Error(`Falha ao carregar data.json (${response.status})`);
    }
    return response.json();
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
}

function relativeDate(isoDate) {
    if (!isoDate) return 'n/a';
    const days = Math.floor((Date.now() - new Date(isoDate)) / 86400000);
    if (days <= 0) return 'hoje';
    if (days === 1) return '1d';
    return `${days}d`;
}

function relativeScanTime(isoDatetime) {
    if (!isoDatetime) return '';
    const mins = Math.floor((Date.now() - new Date(isoDatetime)) / 60000);
    if (mins < 1) return 'agora';
    if (mins < 60) return `ha ${mins}min`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `ha ${hours}h`;
    const days = Math.floor(hours / 24);
    return `ha ${days}d`;
}

function tempClass(isoDate) {
    if (!isoDate) return 'cold';
    const days = Math.floor((Date.now() - new Date(isoDate)) / 86400000);
    if (days <= 1) return 'hot';
    if (days <= 7) return 'warm';
    if (days <= 30) return 'cool';
    return 'cold';
}

function priorityClass(priority) {
    if (priority === 'high') return 'priority-high';
    if (priority === 'low') return 'priority-low';
    return 'priority-medium';
}

function priorityLabel(priority) {
    if (priority === 'high') return 'Alta';
    if (priority === 'low') return 'Baixa';
    return 'Media';
}

function getHealthValue(health, key) {
    if (!health) return null;
    const value = health[key];
    if (value !== null && typeof value === 'object') {
        return cachedCurrentEnvironment ? (value[cachedCurrentEnvironment] ?? null) : null;
    }
    return value;
}

function getActiveFilter() {
    return (dom.searchDesktop?.value || dom.searchMobile?.value || '').trim();
}

function setFilterValue(value) {
    if (dom.searchDesktop && dom.searchDesktop.value !== value) {
        dom.searchDesktop.value = value;
    }
    if (dom.searchMobile && dom.searchMobile.value !== value) {
        dom.searchMobile.value = value;
    }
}

function renderAlerts(projects) {
    const alerts = [];

    projects.forEach(project => {
        if (getHealthValue(project.health, 'claude_memory_portable') === false) {
            alerts.push(`<strong>${escapeHtml(project.name)}</strong>: memoria Claude local (nao portavel)`);
        }
        if (getHealthValue(project.health, 'path_exists') === false) {
            alerts.push(`<strong>${escapeHtml(project.name)}</strong>: caminho nao existe`);
        }
    });

    if (!alerts.length) {
        dom.alertsBar.classList.remove('visible');
        dom.alertsDetails.innerHTML = '';
        dom.alertsCount.textContent = '';
        return;
    }

    dom.alertsBar.classList.add('visible');
    dom.alertsCount.textContent = `${alerts.length} alerta${alerts.length > 1 ? 's' : ''} - toque para ver`;
    dom.alertsDetails.innerHTML = alerts.map(item => `<div class="alert-item">${item}</div>`).join('');
}

function filterMatch(query, ...values) {
    if (!query) return true;
    return values.some(value => {
        if (!value) return false;
        if (Array.isArray(value)) {
            return value.some(item => String(item).toLowerCase().includes(query));
        }
        return String(value).toLowerCase().includes(query);
    });
}

function buildDetailMeta(items) {
    return items.filter(Boolean).join('');
}

function buildIdeaDetailPayload(idea) {
    const meta = buildDetailMeta([
        `<span class="idea-priority ${priorityClass(idea.priority)}">${priorityLabel(idea.priority)}</span>`,
        idea.domain ? `<span class="idea-category-pill">${escapeHtml(idea.domain)}</span>` : '',
        idea.created ? `<span class="tag-pill">${escapeHtml(idea.created)}</span>` : '',
    ]);

    const bodyParts = [];
    if (idea.description) {
        bodyParts.push(`<p>${escapeHtml(idea.description)}</p>`);
    }
    if (idea.notes) {
        bodyParts.push(`<blockquote>${escapeHtml(idea.notes)}</blockquote>`);
    }
    if ((idea.references || []).length) {
        bodyParts.push(
            `<p><strong>Referencias:</strong> ${(idea.references || []).map(ref => escapeHtml(ref)).join(', ')}</p>`
        );
    }

    return {
        kicker: 'Ideia',
        title: idea.title || 'Ideia sem titulo',
        metaHtml: meta,
        bodyHtml: bodyParts.join('') || '<p>Sem detalhes adicionais.</p>',
    };
}

function buildCodexDetailPayload(entry) {
    const meta = buildDetailMeta([
        entry.kind ? `<span class="idea-category-pill">${escapeHtml(entry.kind)}</span>` : '',
        entry.domain ? `<span class="idea-category-pill">${escapeHtml(entry.domain)}</span>` : '',
        entry.updated ? `<span class="tag-pill">${escapeHtml(entry.updated)}</span>` : '',
    ]);

    const parsedBody = typeof marked !== 'undefined'
        ? marked.parse(entry.content || '')
        : `<pre>${escapeHtml(entry.content || '')}</pre>`;

    return {
        kicker: 'Codex',
        title: entry.title || 'Entrada sem titulo',
        metaHtml: meta,
        bodyHtml: parsedBody,
    };
}

function openDetailOverlay(payload) {
    dom.detailPanel.dataset.mode = window.NexusDashboardCore.getOverlayMode(window.innerWidth);
    dom.detailKicker.textContent = payload.kicker || '';
    dom.detailTitle.textContent = payload.title || '';
    dom.detailMeta.innerHTML = payload.metaHtml || '';
    dom.detailBody.innerHTML = payload.bodyHtml || '<p>Sem conteudo.</p>';
    dom.detailOverlay.classList.add('active');
    dom.detailOverlay.setAttribute('aria-hidden', 'false');
}

function closeDetailOverlay() {
    dom.detailOverlay.classList.remove('active');
    dom.detailOverlay.setAttribute('aria-hidden', 'true');
}

function renderIdeas(ideas, filter) {
    const query = filter.toLowerCase();
    let visibleCount = 0;

    if (!ideas.length) {
        dom.ideasGrid.innerHTML = '<div class="empty-state">Nenhuma ideia registrada.</div>';
        dom.ideasCount.textContent = '0';
        return;
    }

    dom.ideasGrid.innerHTML = ideas.map((idea, index) => {
        const matches = filterMatch(
            query,
            idea.title,
            idea.description,
            idea.domain,
            idea.references || []
        );

        if (matches) visibleCount += 1;

        const filteredClass = query && !matches ? ' filtered-out' : '';
        const refs = (idea.references || []).slice(0, 2).map(ref => `<span class="tag-pill">${escapeHtml(ref)}</span>`).join('');

        return `
            <article class="idea-card has-priority-${idea.priority || 'medium'}${filteredClass}" data-idea-index="${index}" tabindex="0">
                <div class="idea-card-header">
                    <span class="idea-priority ${priorityClass(idea.priority)}">${priorityLabel(idea.priority)}</span>
                    ${idea.domain ? `<span class="idea-category-pill">${escapeHtml(idea.domain)}</span>` : ''}
                </div>
                <h3 class="idea-card-title">${escapeHtml(idea.title || 'Sem titulo')}</h3>
                ${idea.description ? `<p class="idea-card-desc">${escapeHtml(idea.description)}</p>` : ''}
                ${refs ? `<div class="idea-card-tags">${refs}</div>` : ''}
                ${idea.notes ? `<p class="idea-card-notes">"${escapeHtml(idea.notes)}"</p>` : ''}
                <div class="idea-card-footer">
                    <span class="idea-card-date">${relativeDate(idea.created)}</span>
                    <span class="tag-pill">abrir detalhe</span>
                </div>
            </article>
        `;
    }).join('');

    dom.ideasCount.textContent = query ? `${visibleCount}/${ideas.length}` : String(ideas.length);

    dom.ideasGrid.querySelectorAll('[data-idea-index]').forEach(card => {
        const openCard = () => openDetailOverlay(buildIdeaDetailPayload(ideas[Number(card.dataset.ideaIndex)]));
        card.addEventListener('click', openCard);
        card.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                openCard();
            }
        });
    });
}

function renderEntityFeed(entries, options) {
    const { container, countElement, emptyMessage, noun, iconFallback, allowDirty } = options;
    const query = getActiveFilter().toLowerCase();
    const sorted = [...entries]
        .filter(entry => entry.status !== 'archived' && entry.status !== 'replaced')
        .sort((a, b) => new Date(b.last_activity || 0) - new Date(a.last_activity || 0));

    if (!sorted.length) {
        container.innerHTML = `<div class="empty-state">${emptyMessage}</div>`;
        countElement.textContent = '0';
        return;
    }

    let visibleCount = 0;
    const html = sorted.map(entry => {
        const matches = filterMatch(
            query,
            entry.name,
            entry.description,
            entry.note,
            entry.domain,
            entry.slug
        );

        if (matches) visibleCount += 1;

        const filteredClass = query && !matches ? ' filtered-out' : '';
        const tc = tempClass(entry.last_activity);
        const memValue = getHealthValue(entry.health, 'claude_memory_portable');

        let primaryHref = '';
        if (entry.url) {
            primaryHref = escapeHtml(entry.url);
        } else if (entry.web?.route) {
            primaryHref = escapeHtml(entry.web.route);
        } else if (entry.repo) {
            primaryHref = `https://github.com/${escapeHtml(entry.repo)}`;
        }

        const nameHtml = primaryHref
            ? `<a class="project-name" href="${primaryHref}" target="_blank" rel="noopener">${escapeHtml(entry.name)}</a>`
            : `<span class="project-name">${escapeHtml(entry.name)}</span>`;

        const memoryBadge = memValue === true
            ? '<span class="badge-memory portable">mem ok</span>'
            : memValue === false
                ? '<span class="badge-memory local-only">mem local</span>'
                : '';

        const metaParts = [
            entry.slug ? `<span class="slug-badge">${escapeHtml(entry.slug)}</span>` : '',
            entry.domain ? `<span class="tag-pill">${escapeHtml(entry.domain)}</span>` : '',
            memoryBadge,
            allowDirty && entry.git?.dirty ? '<span class="project-dirty">dirty</span>' : '',
        ].filter(Boolean).join('');

        return `
            <article class="project-row${filteredClass}">
                <div class="temp-bar ${tc}"></div>
                <div class="project-main">
                    <div class="project-head">
                        <span class="project-icon">${entry.icon || iconFallback}</span>
                        <div class="project-name-wrap">
                            ${nameHtml}
                        </div>
                        <span class="project-date">${relativeDate(entry.last_activity)}</span>
                    </div>
                    ${entry.description ? `<p class="project-desc">${escapeHtml(entry.description)}</p>` : ''}
                    ${metaParts ? `<div class="project-meta">${metaParts}</div>` : ''}
                    ${entry.note ? `<p class="project-note">"${escapeHtml(entry.note)}"</p>` : ''}
                </div>
            </article>
        `;
    }).join('');

    const scanText = relativeScanTime(cachedLastScan);
    container.innerHTML = `${html}<div class="feed-footer">${scanText ? `ultimo scan: ${scanText} - ` : ''}${sorted.length} ${noun}</div>`;
    countElement.textContent = query ? `${visibleCount}/${sorted.length}` : String(sorted.length);
}

function renderProjects(projects) {
    renderEntityFeed(projects, {
        container: dom.projectsFeed,
        countElement: dom.projectsCount,
        emptyMessage: 'Nenhum projeto registrado.',
        noun: 'projetos',
        iconFallback: '📁',
        allowDirty: true,
    });
}

function renderApps(apps) {
    renderEntityFeed(apps, {
        container: dom.appsFeed,
        countElement: dom.appsCount,
        emptyMessage: 'Nenhum app registrado.',
        noun: 'apps',
        iconFallback: '📦',
        allowDirty: false,
    });
}

function renderSkills(skills, filter) {
    const entries = Object.entries(skills || {});
    const query = filter.toLowerCase();

    if (!entries.length) {
        dom.skillsGrid.innerHTML = '<div class="empty-state">Nenhum skill detectado.</div>';
        dom.skillsCount.textContent = '0';
        return;
    }

    let visibleCount = 0;
    dom.skillsGrid.innerHTML = entries.map(([slug, info], index) => {
        const matches = filterMatch(query, slug, info.scope, info.latest, Object.keys(info.versions || {}));
        if (matches) visibleCount += 1;

        const filteredClass = query && !matches ? ' filtered-out' : '';
        const scopeClass = info.scope === 'global' ? 'scope-global' : 'scope-repo';
        const scopeLabel = info.scope === 'global' ? 'global' : 'repo';
        const versions = Object.entries(info.versions || {});
        const latest = info.latest || '';
        const hasGap = versions.some(([, version]) => latest && version !== latest);

        const versionRows = versions.map(([env, version]) => {
            const isOutdated = latest && version !== latest;
            return `
                <tr>
                    <td>${escapeHtml(env)}</td>
                    <td class="${isOutdated ? 'version-outdated' : ''}">
                        ${escapeHtml(version)}
                        ${isOutdated ? '<span class="version-outdated-badge">gap</span>' : ''}
                    </td>
                </tr>
            `;
        }).join('');

        return `
            <article class="skill-card${filteredClass}" style="animation-delay:${index * 0.04}s">
                <div class="skill-card-header">
                    <span class="scope-badge ${scopeClass}">${scopeLabel}</span>
                </div>
                <h3 class="skill-card-title">${escapeHtml(slug)}</h3>
                ${latest ? `<p class="skill-version-latest">latest: ${escapeHtml(latest)}</p>` : ''}
                ${versionRows ? `<table class="skill-version-table"><tbody>${versionRows}</tbody></table>` : ''}
                ${hasGap ? '<div class="skill-gap-warning">versoes divergem entre ambientes</div>' : ''}
            </article>
        `;
    }).join('');

    dom.skillsCount.textContent = query ? `${visibleCount}/${entries.length}` : String(entries.length);
}

function renderEnvironments(environments, filter) {
    const query = filter.toLowerCase();
    const sorted = [...(environments || [])].sort((a, b) => {
        const aCurrent = a.hostname === cachedCurrentEnvironment ? -1 : 1;
        const bCurrent = b.hostname === cachedCurrentEnvironment ? -1 : 1;
        if (aCurrent !== bCurrent) return aCurrent - bCurrent;
        return String(a.hostname || '').localeCompare(String(b.hostname || ''));
    });

    if (!sorted.length) {
        dom.environmentsGrid.innerHTML = '<div class="empty-state">Nenhum ambiente registrado.</div>';
        dom.environmentsCount.textContent = '0';
        return;
    }

    let visibleCount = 0;
    dom.environmentsGrid.innerHTML = sorted.map((env, index) => {
        const matches = filterMatch(query, env.hostname, env.location, env.os, env.absent_projects || []);
        if (matches) visibleCount += 1;

        const filteredClass = query && !matches ? ' filtered-out' : '';
        const currentBadge = env.hostname === cachedCurrentEnvironment
            ? '<span class="env-current-badge">este</span>'
            : '';
        const absent = (env.absent_projects || []).map(project => `<span>${escapeHtml(project)}</span>`).join('');
        const footer = env.last_seen ? `<span class="idea-card-date">${escapeHtml(env.last_seen)}</span>` : '';

        return `
            <article class="env-card${filteredClass}" style="animation-delay:${index * 0.04}s">
                <div class="env-card-header">
                    <h3 class="env-card-title">${escapeHtml(env.hostname || 'desconhecido')} ${currentBadge}</h3>
                </div>
                ${(env.location || env.os) ? `<p class="env-location">${escapeHtml([env.location, env.os].filter(Boolean).join(' - '))}</p>` : ''}
                <div class="env-stats">
                    <span class="env-stat"><strong>${env.project_count ?? '?'}</strong> projetos</span>
                    ${env.last_seen ? `<span class="env-stat">visto <strong>${relativeDate(env.last_seen)}</strong></span>` : ''}
                </div>
                ${absent ? `<div class="env-absent-list">${absent}</div>` : ''}
                <div class="env-card-footer">${footer}</div>
            </article>
        `;
    }).join('');

    dom.environmentsCount.textContent = query ? `${visibleCount}/${sorted.length}` : String(sorted.length);
}

function renderCodex(codex, filter) {
    const query = filter.toLowerCase();

    if (!codex.length) {
        dom.codexGrid.innerHTML = '<div class="empty-state">Nenhuma entrada no Codex.</div>';
        dom.codexCount.textContent = '0';
        return;
    }

    let visibleCount = 0;
    dom.codexGrid.innerHTML = codex.map((entry, index) => {
        const matches = filterMatch(query, entry.title, entry.kind, entry.domain);
        if (matches) visibleCount += 1;

        const filteredClass = query && !matches ? ' filtered-out' : '';

        return `
            <article class="idea-card codex-card has-priority-medium${filteredClass}" data-codex-slug="${escapeHtml(entry.slug)}" tabindex="0" style="animation-delay:${index * 0.04}s">
                <div class="idea-card-header">
                    ${entry.order != null ? `<span class="idea-category-pill">#${entry.order}</span>` : ''}
                    ${entry.kind ? `<span class="idea-category-pill">${escapeHtml(entry.kind)}</span>` : ''}
                    ${entry.domain ? `<span class="idea-category-pill">${escapeHtml(entry.domain)}</span>` : ''}
                </div>
                <h3 class="idea-card-title">📖 ${escapeHtml(entry.title || 'Sem titulo')}</h3>
                <div class="idea-card-footer">
                    <span class="idea-card-date">${relativeDate(entry.updated)}</span>
                    <span class="tag-pill">abrir detalhe</span>
                </div>
            </article>
        `;
    }).join('');

    dom.codexCount.textContent = query ? `${visibleCount}/${codex.length}` : String(codex.length);

    dom.codexGrid.querySelectorAll('[data-codex-slug]').forEach(card => {
        const openCard = () => {
            const entry = codex.find(item => item.slug === card.dataset.codexSlug);
            if (entry) {
                openDetailOverlay(buildCodexDetailPayload(entry));
            }
        };
        card.addEventListener('click', openCard);
        card.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                openCard();
            }
        });
    });
}

function renderActiveSection() {
    const filter = getActiveFilter();

    if (activeTab === 'ideas') {
        renderIdeas(cachedIdeas, filter);
        return;
    }
    if (activeTab === 'projects') {
        renderProjects(cachedProjects);
        return;
    }
    if (activeTab === 'apps') {
        renderApps(cachedApps);
        return;
    }
    if (activeTab === 'skills') {
        renderSkills(cachedSkills, filter);
        return;
    }
    if (activeTab === 'environments') {
        renderEnvironments(cachedEnvironments, filter);
        return;
    }
    renderCodex(cachedCodex, filter);
}

function switchTab(tabId) {
    activeTab = tabId;

    TAB_REGISTRY.forEach(tab => {
        const section = document.getElementById(`${tab.id}-section`);
        if (section) {
            section.hidden = tab.id !== tabId;
        }
    });

    closeMoreMenu();
    renderTabNavigation();
    renderActiveSection();
}

function createTabButton(tab, active, extraClass = '') {
    return `
        <button class="tab-chip${active ? ' active' : ''}${extraClass ? ` ${extraClass}` : ''}" type="button" data-tab="${tab.id}" data-index="${tab.index}">
            <kbd>${tab.index}</kbd>
            <span>${escapeHtml(tab.label)}</span>
        </button>
    `;
}

function measureButtonWidth(label) {
    const probe = document.createElement('button');
    probe.className = 'more-btn';
    probe.type = 'button';
    probe.style.position = 'absolute';
    probe.style.visibility = 'hidden';
    probe.style.pointerEvents = 'none';
    probe.innerHTML = `<span>${escapeHtml(label)}</span>`;
    document.body.appendChild(probe);
    const width = Math.ceil(probe.getBoundingClientRect().width);
    probe.remove();
    return width;
}

function measureTabs() {
    const measureHost = document.createElement('div');
    measureHost.style.position = 'absolute';
    measureHost.style.visibility = 'hidden';
    measureHost.style.pointerEvents = 'none';
    measureHost.style.display = 'flex';
    measureHost.style.gap = '8px';
    document.body.appendChild(measureHost);

    const measured = TAB_REGISTRY.map(tab => {
        const button = document.createElement('button');
        button.className = 'tab-chip';
        button.type = 'button';
        button.innerHTML = `<kbd>${tab.index}</kbd><span>${escapeHtml(tab.label)}</span>`;
        measureHost.appendChild(button);

        return {
            ...tab,
            width: Math.ceil(button.getBoundingClientRect().width),
        };
    });

    measureHost.remove();
    return measured;
}

function closeMoreMenu() {
    dom.moreMenu.classList.remove('active');
    dom.moreMenu.hidden = true;
    dom.moreBtn.setAttribute('aria-expanded', 'false');
}

function toggleMoreMenu() {
    if (!navState.overflow.length) return;

    const isOpen = dom.moreMenu.classList.toggle('active');
    dom.moreMenu.hidden = !isOpen;
    dom.moreBtn.setAttribute('aria-expanded', String(isOpen));
}

function renderTabNavigation() {
    const tabs = measureTabs();
    const availableWidth = dom.primaryTabsShell.clientWidth;
    const moreWidth = measureButtonWidth('Mais');
    navState = window.NexusDashboardCore.splitTabsForLayout(tabs, availableWidth, moreWidth);

    dom.primaryTabs.innerHTML = navState.visible
        .map(tab => createTabButton(tab, tab.id === activeTab))
        .join('');

    const overflowActive = window.NexusDashboardCore.hasActiveOverflowTab(navState.overflow, activeTab);
    dom.moreBtn.hidden = navState.overflow.length === 0;
    dom.moreBtn.classList.toggle('active', overflowActive);

    dom.moreMenu.innerHTML = navState.overflow
        .map(tab => createTabButton(tab, tab.id === activeTab, 'more-item'))
        .join('');

    if (!navState.overflow.length) {
        closeMoreMenu();
    } else if (dom.moreMenu.classList.contains('active')) {
        dom.moreMenu.hidden = false;
        dom.moreBtn.setAttribute('aria-expanded', 'true');
    }
}

function scheduleNavRender() {
    if (resizeScheduled) return;
    resizeScheduled = true;

    window.requestAnimationFrame(() => {
        resizeScheduled = false;
        renderTabNavigation();
        if (dom.detailOverlay.classList.contains('active')) {
            dom.detailPanel.dataset.mode = window.NexusDashboardCore.getOverlayMode(window.innerWidth);
        }
    });
}

function bindNavigationEvents() {
    dom.primaryTabs.addEventListener('click', event => {
        const button = event.target.closest('[data-tab]');
        if (button) switchTab(button.dataset.tab);
    });

    dom.moreMenu.addEventListener('click', event => {
        const button = event.target.closest('[data-tab]');
        if (button) switchTab(button.dataset.tab);
    });

    dom.moreBtn.addEventListener('click', toggleMoreMenu);

    document.addEventListener('click', event => {
        if (
            !event.target.closest('#more-menu') &&
            !event.target.closest('#more-btn')
        ) {
            closeMoreMenu();
        }
    });

    window.addEventListener('resize', scheduleNavRender);
    window.addEventListener('orientationchange', scheduleNavRender);
}

function bindSearchEvents() {
    dom.searchBtn.addEventListener('click', () => {
        dom.searchOverlay.classList.add('active');
        dom.searchMobile.focus();
    });

    dom.searchClose.addEventListener('click', () => {
        dom.searchOverlay.classList.remove('active');
    });

    dom.searchDesktop.addEventListener('input', event => {
        setFilterValue(event.target.value);
        renderActiveSection();
    });

    dom.searchMobile.addEventListener('input', event => {
        setFilterValue(event.target.value);
        renderActiveSection();
    });
}

function bindOverlayEvents() {
    dom.detailClose.addEventListener('click', closeDetailOverlay);
    dom.detailBackdrop.addEventListener('click', closeDetailOverlay);
}

function bindAlertEvents() {
    dom.alertsToggle.addEventListener('click', () => {
        dom.alertsBar.classList.toggle('expanded');
    });
}

function bindKeyboardShortcuts() {
    document.addEventListener('keydown', event => {
        const isTyping = event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA';

        if (event.key === 'Escape') {
            if (dom.detailOverlay.classList.contains('active')) {
                closeDetailOverlay();
                return;
            }
            if (dom.searchOverlay.classList.contains('active')) {
                dom.searchOverlay.classList.remove('active');
                return;
            }
            closeMoreMenu();
            return;
        }

        if (isTyping) return;

        const numericTab = TAB_REGISTRY.find(tab => String(tab.index) === event.key);
        if (numericTab) {
            switchTab(numericTab.id);
        }
    });
}

function renderLoadError(message) {
    const errorHtml = `<div class="empty-state">${escapeHtml(message)}</div>`;
    dom.ideasGrid.innerHTML = errorHtml;
    dom.projectsFeed.innerHTML = errorHtml;
    dom.appsFeed.innerHTML = errorHtml;
    dom.skillsGrid.innerHTML = errorHtml;
    dom.environmentsGrid.innerHTML = errorHtml;
    dom.codexGrid.innerHTML = errorHtml;
}

function cacheDom() {
    dom.primaryTabsShell = document.querySelector('.primary-tabs-shell');
    dom.primaryTabs = document.getElementById('primary-tabs');
    dom.moreBtn = document.getElementById('more-btn');
    dom.moreMenu = document.getElementById('more-menu');
    dom.searchBtn = document.getElementById('search-btn');
    dom.searchDesktop = document.getElementById('search-desk');
    dom.searchOverlay = document.getElementById('search-overlay');
    dom.searchMobile = document.getElementById('search-mobile');
    dom.searchClose = document.getElementById('search-close');
    dom.alertsBar = document.getElementById('alerts-bar');
    dom.alertsToggle = document.getElementById('alerts-toggle');
    dom.alertsDetails = document.getElementById('alerts-details');
    dom.alertsCount = document.getElementById('alerts-count');
    dom.ideasGrid = document.getElementById('ideas-grid');
    dom.projectsFeed = document.getElementById('projects-feed');
    dom.appsFeed = document.getElementById('apps-feed');
    dom.skillsGrid = document.getElementById('skills-grid');
    dom.environmentsGrid = document.getElementById('environments-grid');
    dom.codexGrid = document.getElementById('codex-grid');
    dom.ideasCount = document.getElementById('ideas-count');
    dom.projectsCount = document.getElementById('projects-count');
    dom.appsCount = document.getElementById('apps-count');
    dom.skillsCount = document.getElementById('skills-count');
    dom.environmentsCount = document.getElementById('environments-count');
    dom.codexCount = document.getElementById('codex-count');
    dom.detailOverlay = document.getElementById('detail-overlay');
    dom.detailBackdrop = document.getElementById('detail-backdrop');
    dom.detailPanel = document.getElementById('detail-panel');
    dom.detailClose = document.getElementById('detail-close');
    dom.detailKicker = document.getElementById('detail-kicker');
    dom.detailTitle = document.getElementById('detail-title');
    dom.detailMeta = document.getElementById('detail-meta');
    dom.detailBody = document.getElementById('detail-body');
}

async function init() {
    cacheDom();
    bindNavigationEvents();
    bindSearchEvents();
    bindOverlayEvents();
    bindAlertEvents();
    bindKeyboardShortcuts();

    try {
        const data = await loadData();
        cachedProjects = data.projects || [];
        cachedApps = data.apps || [];
        cachedSkills = data.skills || {};
        cachedEnvironments = data.environments || [];
        cachedCurrentEnvironment = data.current_environment || null;
        cachedIdeas = data.ideas || [];
        cachedCodex = data.codex || [];
        cachedLastScan = data.last_full_scan;

        renderAlerts(cachedProjects);
        renderTabNavigation();
        renderActiveSection();
        document.fonts?.ready?.then(scheduleNavRender);
    } catch (error) {
        console.error(error);
        renderLoadError(error.message || 'Falha ao carregar o dashboard.');
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
