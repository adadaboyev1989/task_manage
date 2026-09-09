(function () {
  let ME = null;
  let ORGS = [];
  const deptFilter = { orgId: null, tab: 'all' };
  const dirFilter = { tab: 'all' };

  const STATUS_LABEL = { pending: 'Kutilmoqda', closed: 'Yopildi', sent: 'Yuborildi', done: 'Bajarildi' };
  const TYPE_LABEL = { control: 'Nazoratda', info: "Ma'lumot" };
  const ROLE_LABEL = { admin: 'Administrator', department: "Bo'lim xodimi", director: 'Direktor' };

  function esc(str) {
    const div = document.createElement('div');
    div.textContent = str ?? '';
    return div.innerHTML;
  }

  function formatDT(stored) {
    if (!stored) return '';
    const [datePart, timePart] = stored.split(' ');
    const [y, m, d] = datePart.split('-');
    const hm = timePart ? timePart.slice(0, 5) : '';
    return `${d}.${m}.${y}${hm ? ' ' + hm : ''}`;
  }

  function isTargetOverdue(target, task) {
    if (task.type !== 'control' || target.status !== 'pending' || !task.deadline_at) return false;
    return new Date(task.deadline_at.replace(' ', 'T')) < new Date();
  }

  function statusBadgeHtml(status, overdue) {
    if (overdue) return `<span class="badge overdue">Muddati o'tgan</span>`;
    return `<span class="badge ${status}">${STATUS_LABEL[status] || status}</span>`;
  }

  // ---------- modal ----------
  const modalRoot = document.getElementById('modal-root');
  function openModal(innerHtml) {
    modalRoot.innerHTML = `<div class="modal-backdrop"><div class="modal">${innerHtml}</div></div>`;
    modalRoot.querySelector('.modal-backdrop').addEventListener('click', (e) => {
      if (e.target.classList.contains('modal-backdrop')) closeModal();
    });
    modalRoot.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', closeModal));
  }
  function closeModal() {
    modalRoot.innerHTML = '';
    if (location.hash.startsWith('#/task/')) history.replaceState(null, '', location.pathname);
  }

  // ---------- task list rendering ----------
  function isAggregateRow(t) {
    return t.targetCount !== undefined;
  }

  function aggregateBadgeHtml(t) {
    if (t.overdue) return `<span class="badge overdue">Muddati o'tgan</span>`;
    if (t.doneCount === t.targetCount) return `<span class="badge closed">Barchasi bajarildi</span>`;
    if (t.doneCount === 0) return `<span class="badge pending">Yuborildi</span>`;
    return `<span class="badge sent">${t.doneCount}/${t.targetCount} bajarildi</span>`;
  }

  function taskRowHtml(t, opts) {
    const aggregate = isAggregateRow(t);
    return `<li class="task-row" data-id="${t.id}">
      <div class="row-top">
        <div>
          <p class="title">${esc(t.title)}</p>
          <div class="meta">
            <span class="badge ${t.type}">${TYPE_LABEL[t.type]}</span>
            ${aggregate ? aggregateBadgeHtml(t) : statusBadgeHtml(t.status, t.overdue)}
            ${aggregate ? `<span>${t.targetCount} ta tashkilotga</span>` : ''}
            ${opts.showOrg && t.orgName ? `<span>${esc(t.orgName)}</span>` : ''}
          </div>
        </div>
      </div>
      ${
        t.deadlineAt || t.createdByName
          ? `<div class="meta">${t.deadlineAt ? `⏰ ${formatDT(t.deadlineAt)}` : ''}${t.createdByName ? `<span>👤 ${esc(t.createdByName)}</span>` : ''}</div>`
          : ''
      }
    </li>`;
  }

  function renderTaskList(list, container, opts) {
    if (!list.length) {
      container.innerHTML = `<div class="empty-state">Topshiriqlar topilmadi</div>`;
      return;
    }
    container.innerHTML = list.map((t) => taskRowHtml(t, opts)).join('');
    container.onclick = (e) => {
      const row = e.target.closest('.task-row');
      if (row) openTaskModal(Number(row.dataset.id));
    };
  }

  function filterTasks(tasks, tab) {
    if (tab === 'active') return tasks.filter((t) => (isAggregateRow(t) ? t.doneCount < t.targetCount : t.status === 'pending' || t.status === 'sent'));
    if (tab === 'overdue') return tasks.filter((t) => t.overdue);
    if (tab === 'done') return tasks.filter((t) => (isAggregateRow(t) ? t.doneCount === t.targetCount : t.status === 'closed' || t.status === 'done'));
    return tasks;
  }

  // ---------- task detail modal ----------
  async function openTaskModal(id) {
    let task;
    try {
      task = await App.api(`/api/tasks/${id}`);
    } catch (err) {
      App.toast(err.message);
      return;
    }
    renderTaskModal(task);
    history.replaceState(null, '', `#/task/${id}`);
  }

  function attachmentRowHtml(a) {
    const icon = a.source === 'telegram' ? '✈️' : '📎';
    const size = a.size ? `${(a.size / 1024).toFixed(0)} KB` : '';
    return `<div class="attachment-item">
      <div>
        <div class="name">${icon} ${esc(a.original_name || 'Telegram xabari')}</div>
        <div class="src">${a.source === 'telegram' ? 'Telegramdan' : 'Fayl'} ${size ? '· ' + size : ''}</div>
      </div>
      <a class="btn secondary small" href="/api/tasks/attachments/${a.id}/download" target="_blank">Yuklab olish</a>
    </div>`;
  }

  function renderTaskModal(task) {
    const isDirector = ME.role === 'director';
    const myTarget = isDirector ? task.targets.find((t) => t.org_id === ME.orgId) : null;

    let targetsHtml = '';
    if (isDirector && myTarget) {
      targetsHtml = `<div class="section-title">Holat</div>
        <p>${statusBadgeHtml(myTarget.status, isTargetOverdue(myTarget, task))}</p>
        ${
          task.type === 'info' && myTarget.status === 'sent'
            ? `<button class="btn success block" id="btn-mark-done">✅ Tushunarli, bajarildi</button>`
            : ''
        }
        ${
          task.type === 'control'
            ? `<p class="hint muted">${myTarget.status === 'closed' ? `Bo'lim tomonidan ${formatDT(myTarget.completed_at)} da nazoratdan yechildi.` : "Ijro nazoratda. Bajarilgach, bo'lim xodimlari nazoratdan yechadi."}</p>`
            : ''
        }`;
    } else {
      const canClose =
        ME.role === 'admin' ||
        (ME.role === 'department' &&
          (task.created_by === ME.id || (task.additionalCloser && task.additionalCloser.id === ME.id)));
      targetsHtml = `<div class="section-title">Tashkilotlar (${task.targets.length})</div>
        <div class="table-wrap"><table class="org-table"><thead><tr><th>Tashkilot</th><th>Holat</th>${task.type === 'control' ? '<th></th>' : ''}</tr></thead>
        <tbody>${task.targets
          .map(
            (t) => `<tr>
              <td>${esc(t.org_name)}</td>
              <td>${statusBadgeHtml(t.status, isTargetOverdue(t, task))}</td>
              ${
                task.type === 'control'
                  ? `<td>${t.status === 'pending' && canClose ? `<button class="btn small danger btn-close-target" data-org="${t.org_id}">Nazoratdan yechish</button>` : ''}</td>`
                  : ''
              }
            </tr>`
          )
          .join('')}</tbody></table></div>
        ${
          task.type === 'control' && !canClose && task.targets.some((t) => t.status === 'pending')
            ? '<p class="hint muted">Faqat shu topshiriqni bergan xodim yoki administrator nazoratdan yecha oladi.</p>'
            : ''
        }
        ${
          task.type === 'control' && task.additionalCloser
            ? `<p class="hint muted">Qo'shimcha ruxsat: ${esc(task.additionalCloser.fullName)}</p>`
            : ''
        }
        ${task.type === 'control' && ME.role === 'admin' ? '<div id="assign-closer-block"></div>' : ''}`;
    }

    openModal(`
      <div class="modal-head">
        <h3 class="modal-title">${esc(task.title)}</h3>
        <button class="close-btn" data-close>&times;</button>
      </div>
      <div class="meta" style="margin-bottom:10px">
        <span class="badge ${task.type}">${TYPE_LABEL[task.type]}</span>
        ${task.deadline_at ? `<span>⏰ ${formatDT(task.deadline_at)}</span>` : ''}
      </div>
      ${task.description ? `<p>${esc(task.description).replace(/\n/g, '<br>')}</p>` : ''}
      ${targetsHtml}
      <div class="section-title">Fayllar (${task.attachments.length})</div>
      <div id="attachments-list">${task.attachments.map(attachmentRowHtml).join('') || '<p class="muted">Hozircha fayl yo\'q</p>'}</div>
      <div style="display:flex; gap:8px; margin-top:10px; flex-wrap:wrap">
        <label class="btn secondary small">
          📎 Fayl biriktirish
          <input type="file" id="file-input" multiple style="display:none" />
        </label>
        <a class="btn secondary small" id="btn-telegram-attach" href="#">✈️ Telegramdan biriktirish</a>
        <button class="btn secondary small" id="btn-share">📤 Ulashish</button>
      </div>
      <p class="hint muted" style="margin-top:6px">Yaratdi: ${esc(task.creator?.full_name || '—')} · ${formatDT(task.created_at)}</p>
    `);

    if (isDirector && myTarget && task.type === 'info' && myTarget.status === 'sent') {
      document.getElementById('btn-mark-done').onclick = async () => {
        try {
          await App.api(`/api/tasks/${task.id}/targets/${myTarget.org_id}/done`, { method: 'PATCH' });
          App.toast("Bajarildi deb belgilandi ✅");
          closeModal();
          refreshCurrentView();
        } catch (err) {
          App.toast(err.message);
        }
      };
    }

    modalRoot.querySelectorAll('.btn-close-target').forEach((btn) => {
      btn.onclick = async () => {
        try {
          await App.api(`/api/tasks/${task.id}/targets/${btn.dataset.org}/close`, { method: 'PATCH' });
          App.toast('Nazoratdan yechildi ✅');
          openTaskModal(task.id);
          refreshCurrentView();
        } catch (err) {
          App.toast(err.message);
        }
      };
    });

    document.getElementById('file-input').onchange = async (e) => {
      const files = [...e.target.files];
      if (!files.length) return;
      const fd = new FormData();
      files.forEach((f) => fd.append('files', f));
      try {
        await App.api(`/api/tasks/${task.id}/attachments`, { method: 'POST', body: fd });
        App.toast(files.length > 1 ? `${files.length} ta fayl biriktirildi ✅` : 'Fayl biriktirildi ✅');
        openTaskModal(task.id);
      } catch (err) {
        App.toast(err.message);
      }
    };

    // Fetch the deep link up front and set it as a real href, so the eventual click is a
    // direct anchor navigation (not a JS-triggered one) — that's what reliably hands off
    // to the Telegram app on mobile browsers for a https://t.me/... link.
    const attachBtn = document.getElementById('btn-telegram-attach');
    let attachDeepLink = null;
    let attachError = null;
    App.api(`/api/tasks/${task.id}/attach-link`)
      .then(({ deepLink, botConfigured }) => {
        if (!botConfigured) {
          attachError = 'Telegram bot hali sozlanmagan';
        } else {
          attachDeepLink = deepLink;
          attachBtn.href = deepLink;
        }
      })
      .catch((err) => {
        attachError = err.message;
      });

    attachBtn.onclick = (e) => {
      if (!attachDeepLink) {
        e.preventDefault();
        App.toast(attachError || 'Havola hali tayyor emas, birozdan so\'ng qayta urining');
        return;
      }
      App.toast('Telegramda xabarni forward qiling');
    };

    document.getElementById('btn-share').onclick = () => shareTaskToTelegram(task);

    if (task.type === 'control' && ME.role === 'admin') {
      renderAssignCloserBlock(task);
    }
  }

  async function renderAssignCloserBlock(task) {
    const block = document.getElementById('assign-closer-block');
    if (!block) return;
    let users;
    try {
      users = await App.api('/api/users?role=department');
    } catch (err) {
      return;
    }
    const options = users
      .filter((u) => u.id !== task.created_by)
      .map(
        (u) =>
          `<option value="${u.id}" ${task.additionalCloser && task.additionalCloser.id === u.id ? 'selected' : ''}>${esc(u.fullName)}</option>`
      )
      .join('');
    block.innerHTML = `<div class="section-title">Qo'shimcha nazoratdan yechish huquqi</div>
      <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center">
        <select id="assign-closer-select">
          <option value="">— Tanlanmagan —</option>
          ${options}
        </select>
        <button class="btn secondary small" id="btn-assign-closer-save">Saqlash</button>
      </div>`;
    document.getElementById('btn-assign-closer-save').onclick = async () => {
      const val = document.getElementById('assign-closer-select').value;
      try {
        await App.api(`/api/tasks/${task.id}/assign-closer`, {
          method: 'PATCH',
          body: { userId: val ? Number(val) : null },
        });
        App.toast('Saqlandi ✅');
        openTaskModal(task.id);
      } catch (err) {
        App.toast(err.message);
      }
    };
  }

  async function shareTaskToTelegram(task) {
    const lines = [task.title];
    if (task.description) lines.push(task.description);
    if (task.deadline_at) lines.push(`⏰ Muddat: ${formatDT(task.deadline_at)}`);
    const text = lines.join('\n\n');
    const shareUrl = `${location.origin}/#/task/${task.id}`;

    let files = [];
    if (task.attachments.length && navigator.canShare) {
      try {
        files = await Promise.all(
          task.attachments.map(async (a) => {
            const res = await fetch(`/api/tasks/attachments/${a.id}/download`, { credentials: 'include' });
            const blob = await res.blob();
            const name = a.original_name || `matn-${a.id}.txt`;
            return new File([blob], name, { type: blob.type || 'application/octet-stream' });
          })
        );
        if (!navigator.canShare({ files })) files = [];
      } catch (err) {
        console.error('fayllarni ulashishga tayyorlashda xato', err);
        files = [];
      }
    }

    if (navigator.share) {
      try {
        await navigator.share(files.length ? { title: task.title, text, files } : { title: task.title, text, url: shareUrl });
        return;
      } catch (err) {
        if (err.name === 'AbortError') return;
        console.error('ulashish muvaffaqiyatsiz', err);
      }
    }

    // Fallback for browsers without the Web Share API (mainly desktop): open Telegram's
    // own share dialog so the user can still pick a chat to forward the text+link to.
    window.open(`https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(text)}`, '_blank');
    if (task.attachments.length) {
      App.toast("Fayllarni alohida yuklab olib, Telegram orqali qo'lda yuboring");
    }
  }

  // ---------- director view ----------
  async function renderDirector() {
    const [stats, tasks] = await Promise.all([App.api('/api/stats/me'), App.api('/api/tasks')]);
    const app = document.getElementById('app');
    app.innerHTML = `
      <div class="stat-grid">
        <div class="stat-tile accent-primary"><div class="num">${stats.total}</div><div class="label">Jami</div></div>
        <div class="stat-tile accent-warning"><div class="num">${stats.controlPending + stats.infoPending}</div><div class="label">Faol</div></div>
        <div class="stat-tile accent-danger"><div class="num">${stats.overdue}</div><div class="label">Muddati o'tgan</div></div>
        <div class="stat-tile accent-success"><div class="num">${stats.controlClosed + stats.infoDone}</div><div class="label">Bajarilgan</div></div>
      </div>
      <div class="tabs" id="tabs">
        <button class="tab-btn ${dirFilter.tab === 'all' ? 'active' : ''}" data-f="all">Barchasi</button>
        <button class="tab-btn ${dirFilter.tab === 'active' ? 'active' : ''}" data-f="active">Faol</button>
        <button class="tab-btn ${dirFilter.tab === 'overdue' ? 'active' : ''}" data-f="overdue">Muddati o'tgan</button>
        <button class="tab-btn ${dirFilter.tab === 'done' ? 'active' : ''}" data-f="done">Bajarilgan</button>
      </div>
      <ul class="task-list" id="task-list"></ul>
    `;

    function apply() {
      renderTaskList(filterTasks(tasks, dirFilter.tab), document.getElementById('task-list'), { showOrg: false });
    }
    document.querySelectorAll('#tabs .tab-btn').forEach((b) =>
      b.addEventListener('click', () => {
        document.querySelectorAll('#tabs .tab-btn').forEach((x) => x.classList.remove('active'));
        b.classList.add('active');
        dirFilter.tab = b.dataset.f;
        apply();
      })
    );
    apply();
  }

  // ---------- department/admin view ----------
  function orgTableHtml(orgs) {
    return `<div class="table-wrap"><table class="org-table">
      <thead><tr><th>Nomi</th><th>Turi</th><th>Nazoratda</th><th>Muddati o'tgan</th><th>Ma'lumot</th><th>Direktor</th></tr></thead>
      <tbody>${orgs
        .map(
          (o) => `<tr class="org-row" data-org="${o.id}" style="cursor:pointer">
        <td>${esc(o.name)}</td>
        <td>${o.type === 'school' ? 'Maktab' : "Bog'cha"}</td>
        <td>${o.controlPending}</td>
        <td>${o.overdue ? `<span class="badge overdue">${o.overdue}</span>` : 0}</td>
        <td>${o.infoPending}</td>
        <td>${o.director ? esc(o.director.fullName) + (o.director.telegramLinked ? ' ✅' : ' ⚠️') : '—'}</td>
      </tr>`
        )
        .join('')}</tbody>
    </table></div>`;
  }

  async function renderDepartment() {
    const [overview, orgs] = await Promise.all([App.api('/api/stats/overview'), App.api('/api/orgs')]);
    ORGS = orgs;
    const app = document.getElementById('app');
    app.innerHTML = `
      <div class="stat-grid">
        <div class="stat-tile accent-primary"><div class="num">${overview.totals.total}</div><div class="label">Jami topshiriqlar</div></div>
        <div class="stat-tile accent-warning"><div class="num">${overview.totals.controlPending}</div><div class="label">Nazoratda</div></div>
        <div class="stat-tile accent-danger"><div class="num">${overview.totals.overdue}</div><div class="label">Muddati o'tgan</div></div>
        <div class="stat-tile accent-success"><div class="num">${overview.totals.controlClosed + overview.totals.infoDone}</div><div class="label">Bajarilgan</div></div>
      </div>
      <p class="muted" style="margin-top:-8px">🏫 ${overview.schoolCount} ta maktab · 🧸 ${overview.kindergartenCount} ta bog'cha</p>
      <div class="tabs">
        <button class="tab-btn" data-tab="overview">Tashkilotlar</button>
        <button class="tab-btn" data-tab="tasks">Topshiriqlar</button>
      </div>
      <div id="tab-content"></div>
    `;

    const tabButtons = app.querySelectorAll('.tabs .tab-btn');
    let activeTab = 'overview';

    function setTab(tab) {
      activeTab = tab;
      tabButtons.forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
      if (tab === 'overview') renderOverviewTab();
      else renderTasksTab();
    }
    tabButtons.forEach((b) => b.addEventListener('click', () => setTab(b.dataset.tab)));

    function renderOverviewTab() {
      document.getElementById('tab-content').innerHTML = orgTableHtml(overview.perOrg);
      document.querySelectorAll('.org-row').forEach((row) => {
        row.addEventListener('click', () => {
          deptFilter.orgId = Number(row.dataset.org);
          setTab('tasks');
        });
      });
    }

    async function renderTasksTab() {
      const content = document.getElementById('tab-content');
      const orgName = deptFilter.orgId ? ORGS.find((o) => o.id === deptFilter.orgId)?.name : null;
      content.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:10px">
          <div class="tabs" id="status-tabs" style="margin:0">
            <button class="tab-btn ${deptFilter.tab === 'all' ? 'active' : ''}" data-f="all">Barchasi</button>
            <button class="tab-btn ${deptFilter.tab === 'active' ? 'active' : ''}" data-f="active">Faol</button>
            <button class="tab-btn ${deptFilter.tab === 'overdue' ? 'active' : ''}" data-f="overdue">Muddati o'tgan</button>
            <button class="tab-btn ${deptFilter.tab === 'done' ? 'active' : ''}" data-f="done">Bajarilgan</button>
          </div>
          <button class="btn" id="btn-new-task">+ Yangi topshiriq</button>
        </div>
        ${orgName ? `<p class="muted">Filtr: <b>${esc(orgName)}</b> <a href="#" id="clear-org-filter">(tozalash)</a></p>` : ''}
        <ul class="task-list" id="task-list"></ul>
      `;

      const tasks = await App.api(`/api/tasks${deptFilter.orgId ? `?orgId=${deptFilter.orgId}` : ''}`);
      renderTaskList(filterTasks(tasks, deptFilter.tab), document.getElementById('task-list'), { showOrg: !deptFilter.orgId });

      content.querySelectorAll('#status-tabs .tab-btn').forEach((b) =>
        b.addEventListener('click', () => {
          deptFilter.tab = b.dataset.f;
          renderTasksTab();
        })
      );
      const clearLink = document.getElementById('clear-org-filter');
      if (clearLink) clearLink.addEventListener('click', (e) => { e.preventDefault(); deptFilter.orgId = null; renderTasksTab(); });
      document.getElementById('btn-new-task').addEventListener('click', openCreateTaskModal);
    }

    setTab('overview');
  }

  function openCreateTaskModal() {
    const schools = ORGS.filter((o) => o.type === 'school');
    const kindergartens = ORGS.filter((o) => o.type === 'kindergarten');

    openModal(`
      <div class="modal-head">
        <h3 class="modal-title">Yangi topshiriq</h3>
        <button class="close-btn" data-close>&times;</button>
      </div>
      <form id="create-task-form">
        <div class="field">
          <label>Sarlavha</label>
          <input type="text" id="f-title" required maxlength="200" />
        </div>
        <div class="field">
          <label>Tavsif</label>
          <textarea id="f-description" maxlength="4000"></textarea>
        </div>
        <div class="field">
          <label>Turi</label>
          <select id="f-type">
            <option value="control">🔴 Ijrosi ta'minlanadigan (nazoratda)</option>
            <option value="info">ℹ️ Ma'lumot uchun</option>
          </select>
        </div>
        <div class="field" id="deadline-field">
          <label>Bajarish muddati</label>
          <input type="datetime-local" id="f-deadline" />
        </div>
        <div class="field">
          <label>Kimlarga yuboriladi</label>
          <div style="display:flex; gap:6px; margin-bottom:8px; flex-wrap:wrap">
            <button type="button" class="btn secondary small" data-quick="school">Barcha maktablar</button>
            <button type="button" class="btn secondary small" data-quick="kindergarten">Barcha bog'chalar</button>
            <button type="button" class="btn secondary small" data-quick="all">Hammasi</button>
            <button type="button" class="btn secondary small" data-quick="none">Tozalash</button>
          </div>
          <div class="checkbox-grid" id="org-checkboxes">
            ${[...schools, ...kindergartens]
              .map((o) => `<label><input type="checkbox" value="${o.id}" /> ${esc(o.name)}</label>`)
              .join('')}
          </div>
        </div>
        <div class="field">
          <label>Fayl biriktirish <span class="muted">(ixtiyoriy, bir nechta tanlash mumkin)</span></label>
          <input type="file" id="f-file" multiple />
        </div>
        <button class="btn block" type="submit">Yuborish</button>
      </form>
    `);

    const typeSelect = document.getElementById('f-type');
    const deadlineField = document.getElementById('deadline-field');
    function syncDeadlineVisibility() {
      deadlineField.style.display = typeSelect.value === 'control' ? '' : 'none';
    }
    typeSelect.onchange = syncDeadlineVisibility;
    syncDeadlineVisibility();

    const checkboxes = () => [...document.querySelectorAll('#org-checkboxes input[type=checkbox]')];
    document.querySelectorAll('[data-quick]').forEach((btn) => {
      btn.onclick = () => {
        const mode = btn.dataset.quick;
        checkboxes().forEach((cb) => {
          const org = ORGS.find((o) => String(o.id) === cb.value);
          if (mode === 'none') cb.checked = false;
          else if (mode === 'all') cb.checked = true;
          else cb.checked = org?.type === mode;
        });
      };
    });

    document.getElementById('create-task-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const orgIds = checkboxes().filter((cb) => cb.checked).map((cb) => Number(cb.value));
      if (!orgIds.length) return App.toast('Kamida bitta tashkilot tanlang');

      const payload = {
        title: document.getElementById('f-title').value,
        description: document.getElementById('f-description').value,
        type: typeSelect.value,
        deadlineAt: document.getElementById('f-deadline').value || null,
        orgIds,
      };
      try {
        const task = await App.api('/api/tasks', { method: 'POST', body: payload });

        const files = [...document.getElementById('f-file').files];
        if (files.length) {
          const fd = new FormData();
          files.forEach((f) => fd.append('files', f));
          try {
            await App.api(`/api/tasks/${task.id}/attachments`, { method: 'POST', body: fd });
          } catch (err) {
            App.toast(`Topshiriq yuborildi, lekin fayl biriktirilmadi: ${err.message}`);
            closeModal();
            refreshCurrentView();
            return;
          }
        }

        App.toast('Topshiriq yuborildi ✅');
        closeModal();
        refreshCurrentView();
      } catch (err) {
        App.toast(err.message);
      }
    });
  }

  // ---------- shell ----------
  function refreshCurrentView() {
    if (ME.role === 'director') renderDirector();
    else renderDepartment();
  }

  function setupInstallButton() {
    const btn = document.getElementById('btn-install');
    function refresh() {
      btn.classList.toggle('hidden', !App.canInstall());
    }
    document.addEventListener('pwa-install-available', refresh);
    refresh();
    btn.onclick = async () => {
      await App.promptInstall();
      refresh();
    };
  }

  async function logout() {
    await App.api('/api/auth/logout', { method: 'POST' });
    location.href = '/login';
  }

  async function init() {
    let user;
    try {
      ({ user } = await App.api('/api/auth/me'));
    } catch {
      location.href = '/login';
      return;
    }
    ME = user;
    document.getElementById('user-chip').textContent = `${ME.fullName} · ${ROLE_LABEL[ME.role]}`;
    document.getElementById('brand-title').textContent = ME.role === 'director' ? 'Mening topshiriqlarim' : 'Topshiriqlar nazorati';
    document.getElementById('btn-logout').onclick = logout;
    document.getElementById('btn-notify').onclick = () => App.enablePushNotifications();
    if (ME.role === 'admin') document.getElementById('link-admin').classList.remove('hidden');
    setupInstallButton();

    if (ME.role === 'director') await renderDirector();
    else await renderDepartment();

    const match = location.hash.match(/^#\/task\/(\d+)/);
    if (match) openTaskModal(Number(match[1]));
  }

  init();
})();
