(function () {
  const ROLE_LABEL = { admin: 'Administrator', department: "Bo'lim xodimi", director: 'Direktor' };
  let ORGS = [];
  let USERS = [];

  function esc(str) {
    const div = document.createElement('div');
    div.textContent = str ?? '';
    return div.innerHTML;
  }
  function formatDT(stored) {
    if (!stored) return '';
    const [datePart, timePart] = stored.split(' ');
    const [y, m, d] = datePart.split('-');
    return `${d}.${m}.${y}${timePart ? ' ' + timePart.slice(0, 5) : ''}`;
  }

  const modalRoot = document.getElementById('modal-root');
  function openModal(html) {
    modalRoot.innerHTML = `<div class="modal-backdrop"><div class="modal">${html}</div></div>`;
    modalRoot.querySelector('.modal-backdrop').addEventListener('click', (e) => {
      if (e.target.classList.contains('modal-backdrop')) closeModal();
    });
    modalRoot.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', closeModal));
  }
  function closeModal() {
    modalRoot.innerHTML = '';
  }

  // ---------- Users tab ----------
  async function loadUsers() {
    USERS = await App.api('/api/users');
  }

  function usersTableHtml() {
    return `
      <p class="hint muted" style="margin-bottom:10px">
        Foydalanuvchi qo'shishdan oldin ularga botga (<code>/start</code>) yozib, chiqqan Telegram ID'ni sizga
        yuborishni so'rang.
      </p>
      <div style="display:flex; justify-content:flex-end; margin-bottom:10px">
        <button class="btn" id="btn-new-user">+ Yangi foydalanuvchi</button>
      </div>
      <div class="table-wrap"><table class="org-table">
        <thead><tr><th>Ism</th><th>Rol</th><th>Tashkilot</th><th>Telefon</th><th>Telegram</th><th>Login</th><th>Holat</th><th></th></tr></thead>
        <tbody>${USERS.map(
          (u) => `<tr>
            <td>${esc(u.fullName)}</td>
            <td>${ROLE_LABEL[u.role]}</td>
            <td>${esc(u.orgName || '—')}</td>
            <td>${esc(u.phone || '—')}</td>
            <td>${
              u.telegramUsername
                ? '✅ @' + esc(u.telegramUsername)
                : u.telegramChatId
                ? `ID: <b>${esc(u.telegramChatId)}</b>`
                : '<span class="muted">Kiritilmagan</span>'
            }</td>
            <td>${u.role === 'admin' ? (u.username ? `🔑 ${esc(u.username)}` : '<span class="muted">Yo\'q</span>') : '<span class="muted">—</span>'}</td>
            <td>${u.isActive ? '<span class="badge closed">Faol</span>' : '<span class="badge overdue">Faolsiz</span>'}</td>
            <td style="white-space:nowrap">
              <button class="btn secondary small btn-edit-user" data-id="${u.id}">Tahrirlash</button>
              <button class="btn secondary small btn-edit-telegram" data-id="${u.id}" data-tgid="${esc(u.telegramChatId)}">Telegram ID</button>
              ${u.role === 'admin' ? `<button class="btn secondary small btn-edit-credentials" data-id="${u.id}" data-username="${esc(u.username || '')}">Login-parol</button>` : ''}
              <button class="btn secondary small btn-toggle" data-id="${u.id}" data-active="${u.isActive ? 1 : 0}">${u.isActive ? 'Bloklash' : 'Faollashtirish'}</button>
              <button class="btn danger small btn-delete-user" data-id="${u.id}">O'chirish</button>
            </td>
          </tr>`
        ).join('')}</tbody>
      </table></div>`;
  }

  async function renderUsersTab() {
    const content = document.getElementById('tab-content');
    content.innerHTML = `<div class="empty-state">Yuklanmoqda...</div>`;
    await Promise.all([loadUsers(), loadOrgsIfNeeded()]);
    content.innerHTML = usersTableHtml();

    document.getElementById('btn-new-user').onclick = openCreateUserModal;
    content.querySelectorAll('.btn-edit-user').forEach((btn) => {
      btn.onclick = () => openEditUserModal(btn.dataset.id);
    });
    content.querySelectorAll('.btn-edit-telegram').forEach((btn) => {
      btn.onclick = () => openEditTelegramIdModal(btn.dataset.id, btn.dataset.tgid);
    });
    content.querySelectorAll('.btn-edit-credentials').forEach((btn) => {
      btn.onclick = () => openEditCredentialsModal(btn.dataset.id, btn.dataset.username);
    });
    content.querySelectorAll('.btn-toggle').forEach((btn) => {
      btn.onclick = async () => {
        await App.api(`/api/users/${btn.dataset.id}`, { method: 'PATCH', body: { isActive: btn.dataset.active !== '1' } });
        renderUsersTab();
      };
    });
    content.querySelectorAll('.btn-delete-user').forEach((btn) => {
      btn.onclick = async () => {
        const user = USERS.find((u) => String(u.id) === btn.dataset.id);
        if (!confirm(`"${user?.fullName || ''}" foydalanuvchisini o'chirmoqchimisiz? Bu amalni qaytarib bo'lmaydi.`)) return;
        try {
          const result = await App.api(`/api/users/${btn.dataset.id}`, { method: 'DELETE' });
          App.toast(
            result.anonymized
              ? "Foydalanuvchi o'chirildi ✅ (topshiriqlar tarixi saqlab qolindi)"
              : "Foydalanuvchi butunlay o'chirildi ✅"
          );
          renderUsersTab();
        } catch (err) {
          App.toast(err.message);
        }
      };
    });
  }

  function openEditUserModal(userId) {
    const user = USERS.find((u) => String(u.id) === String(userId));
    if (!user) return;
    const freeOrgs = ORGS.filter((o) => !o.director || o.director.id === user.id);

    openModal(`
      <div class="modal-head"><h3 class="modal-title">Foydalanuvchini tahrirlash</h3><button class="close-btn" data-close>&times;</button></div>
      <form id="edit-user-form">
        <div class="field"><label>To'liq ism</label><input type="text" id="f-name" value="${esc(user.fullName)}" required /></div>
        <div class="field"><label>Telefon</label><input type="tel" id="f-phone" value="${esc(user.phone || '')}" placeholder="+998" /></div>
        ${
          user.role === 'director'
            ? `<div class="field"><label>Tashkilot</label>
                <select id="f-org">${freeOrgs.map((o) => `<option value="${o.id}" ${o.id === user.orgId ? 'selected' : ''}>${esc(o.name)} (${o.type === 'school' ? 'Maktab' : "Bog'cha"})</option>`).join('')}</select>
              </div>`
            : ''
        }
        <button class="btn block" type="submit">Saqlash</button>
      </form>
    `);

    document.getElementById('edit-user-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        fullName: document.getElementById('f-name').value,
        phone: document.getElementById('f-phone').value,
      };
      if (user.role === 'director') payload.orgId = Number(document.getElementById('f-org').value);
      try {
        await App.api(`/api/users/${userId}`, { method: 'PATCH', body: payload });
        closeModal();
        App.toast('Saqlandi ✅');
        renderUsersTab();
      } catch (err) {
        App.toast(err.message);
      }
    });
  }

  function openEditCredentialsModal(userId, currentUsername) {
    openModal(`
      <div class="modal-head"><h3 class="modal-title">Login-parol</h3><button class="close-btn" data-close>&times;</button></div>
      <form id="edit-credentials-form">
        <div class="field">
          <label>Login</label>
          <input type="text" id="f-username" value="${esc(currentUsername)}" required pattern="[a-z0-9_.]{3,32}" />
        </div>
        <div class="field">
          <label>Yangi parol</label>
          <input type="password" id="f-password" placeholder="Kamida 6 belgi" minlength="6" required autocomplete="new-password" />
        </div>
        <button class="btn block" type="submit">Saqlash</button>
      </form>
    `);
    document.getElementById('edit-credentials-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        await App.api(`/api/users/${userId}`, {
          method: 'PATCH',
          body: { username: document.getElementById('f-username').value.trim(), password: document.getElementById('f-password').value },
        });
        closeModal();
        App.toast('Login-parol yangilandi ✅');
        renderUsersTab();
      } catch (err) {
        App.toast(err.message);
      }
    });
  }

  function openEditTelegramIdModal(userId, currentId) {
    openModal(`
      <div class="modal-head"><h3 class="modal-title">Telegram ID</h3><button class="close-btn" data-close>&times;</button></div>
      <form id="edit-telegram-form">
        <div class="field">
          <label>Telegram ID</label>
          <input type="text" id="f-telegram-id" value="${esc(currentId)}" inputmode="numeric" required />
          <span class="hint">Foydalanuvchi botga /start yozganda o'z ID'sini ko'radi</span>
        </div>
        <button class="btn block" type="submit">Saqlash</button>
      </form>
    `);
    document.getElementById('edit-telegram-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        await App.api(`/api/users/${userId}`, { method: 'PATCH', body: { telegramId: document.getElementById('f-telegram-id').value.trim() } });
        closeModal();
        App.toast('Telegram ID yangilandi ✅');
        renderUsersTab();
      } catch (err) {
        App.toast(err.message);
      }
    });
  }

  function openCreateUserModal() {
    const freeOrgs = ORGS.filter((o) => !o.director);
    openModal(`
      <div class="modal-head"><h3 class="modal-title">Yangi foydalanuvchi</h3><button class="close-btn" data-close>&times;</button></div>
      <form id="create-user-form">
        <div class="field"><label>To'liq ism</label><input type="text" id="f-name" required /></div>
        <div class="field"><label>Rol</label>
          <select id="f-role">
            <option value="director">Direktor (maktab/bog'cha)</option>
            <option value="department">Bo'lim xodimi</option>
            <option value="admin">Administrator</option>
          </select>
        </div>
        <div class="field" id="org-field"><label>Tashkilot</label>
          <select id="f-org">${freeOrgs.map((o) => `<option value="${o.id}">${esc(o.name)} (${o.type === 'school' ? 'Maktab' : "Bog'cha"})</option>`).join('') || '<option value="">Bo\'sh tashkilot yo\'q</option>'}</select>
        </div>
        <div class="field" id="telegram-field">
          <label>Telegram ID <span id="telegram-optional-hint" class="hidden muted">(ixtiyoriy — login-parol ham qo'yish mumkin)</span></label>
          <input type="text" id="f-telegram-id" inputmode="numeric" placeholder="Masalan: 123456789" />
          <span class="hint">Foydalanuvchi shu botga /start yozganda o'z ID'sini ko'radi — o'shani shu yerga kiriting</span>
        </div>
        <div class="field hidden" id="credentials-field">
          <label>Login-parol (ixtiyoriy, admin panelga to'g'ridan-to'g'ri kirish uchun)</label>
          <input type="text" id="f-username" placeholder="Login (kichik harflar, raqam)" pattern="[a-z0-9_.]{3,32}" style="margin-bottom:8px" />
          <input type="password" id="f-password" placeholder="Parol (kamida 6 belgi)" minlength="6" autocomplete="new-password" />
        </div>
        <div class="field"><label>Telefon</label><input type="tel" id="f-phone" placeholder="+998" /></div>
        <button class="btn block" type="submit">Yaratish</button>
      </form>
    `);

    const roleSelect = document.getElementById('f-role');
    const orgField = document.getElementById('org-field');
    const telegramInput = document.getElementById('f-telegram-id');
    const telegramOptionalHint = document.getElementById('telegram-optional-hint');
    const credentialsField = document.getElementById('credentials-field');
    function sync() {
      const isAdmin = roleSelect.value === 'admin';
      orgField.style.display = roleSelect.value === 'director' ? '' : 'none';
      telegramInput.required = !isAdmin;
      telegramOptionalHint.classList.toggle('hidden', !isAdmin);
      credentialsField.classList.toggle('hidden', !isAdmin);
    }
    roleSelect.onchange = sync;
    sync();

    document.getElementById('create-user-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        fullName: document.getElementById('f-name').value,
        role: roleSelect.value,
        phone: document.getElementById('f-phone').value,
        telegramId: telegramInput.value.trim(),
        orgId: roleSelect.value === 'director' ? Number(document.getElementById('f-org').value) : undefined,
      };
      if (roleSelect.value === 'admin') {
        const username = document.getElementById('f-username').value.trim();
        const password = document.getElementById('f-password').value;
        if (username || password) {
          payload.username = username;
          payload.password = password;
        }
      }
      try {
        await App.api('/api/users', { method: 'POST', body: payload });
        closeModal();
        App.toast('Foydalanuvchi yaratildi ✅');
        renderUsersTab();
      } catch (err) {
        App.toast(err.message);
      }
    });
  }

  // ---------- Orgs tab ----------
  async function loadOrgsIfNeeded() {
    ORGS = await App.api('/api/orgs');
  }

  function orgsTableHtml() {
    return `
      <div style="display:flex; justify-content:flex-end; margin-bottom:10px">
        <button class="btn" id="btn-new-org">+ Yangi tashkilot</button>
      </div>
      <div class="table-wrap"><table class="org-table">
        <thead><tr><th>Nomi</th><th>Turi</th><th>Manzil</th><th>Direktor</th></tr></thead>
        <tbody>${ORGS.map(
          (o) => `<tr>
            <td>${esc(o.name)}</td>
            <td>${o.type === 'school' ? 'Maktab' : "Bog'cha"}</td>
            <td>${esc(o.address || '—')}</td>
            <td>${o.director ? esc(o.director.fullName) + (o.director.telegramLinked ? ' ✅' : ' ⚠️') : '<span class="muted">Tayinlanmagan</span>'}</td>
          </tr>`
        ).join('')}</tbody>
      </table></div>`;
  }

  async function renderOrgsTab() {
    const content = document.getElementById('tab-content');
    content.innerHTML = `<div class="empty-state">Yuklanmoqda...</div>`;
    await loadOrgsIfNeeded();
    content.innerHTML = orgsTableHtml();
    document.getElementById('btn-new-org').onclick = openCreateOrgModal;
  }

  function openCreateOrgModal() {
    openModal(`
      <div class="modal-head"><h3 class="modal-title">Yangi tashkilot</h3><button class="close-btn" data-close>&times;</button></div>
      <form id="create-org-form">
        <div class="field"><label>Nomi</label><input type="text" id="o-name" required /></div>
        <div class="field"><label>Turi</label>
          <select id="o-type"><option value="school">Maktab</option><option value="kindergarten">Bog'cha</option></select>
        </div>
        <div class="field"><label>Manzil</label><input type="text" id="o-address" /></div>
        <button class="btn block" type="submit">Yaratish</button>
      </form>
    `);
    document.getElementById('create-org-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        await App.api('/api/orgs', {
          method: 'POST',
          body: { name: document.getElementById('o-name').value, type: document.getElementById('o-type').value, address: document.getElementById('o-address').value },
        });
        closeModal();
        renderOrgsTab();
        App.toast('Tashkilot yaratildi ✅');
      } catch (err) {
        App.toast(err.message);
      }
    });
  }

  // ---------- Stats tab ----------
  async function renderStatsTab() {
    const content = document.getElementById('tab-content');
    content.innerHTML = `<div class="empty-state">Yuklanmoqda...</div>`;
    const overview = await App.api('/api/stats/overview');
    content.innerHTML = `
      <div class="stat-grid">
        <div class="stat-tile accent-primary"><div class="num">${overview.totals.total}</div><div class="label">Jami topshiriqlar</div></div>
        <div class="stat-tile accent-warning"><div class="num">${overview.totals.controlPending}</div><div class="label">Nazoratda</div></div>
        <div class="stat-tile accent-danger"><div class="num">${overview.totals.overdue}</div><div class="label">Muddati o'tgan</div></div>
        <div class="stat-tile accent-success"><div class="num">${overview.totals.controlClosed}</div><div class="label">Yopilgan (nazorat)</div></div>
        <div class="stat-tile accent-primary"><div class="num">${overview.totals.infoPending}</div><div class="label">Ma'lumot kutilmoqda</div></div>
        <div class="stat-tile accent-success"><div class="num">${overview.totals.infoDone}</div><div class="label">Ma'lumot bajarildi</div></div>
      </div>
      <p class="muted">🏫 ${overview.schoolCount} ta maktab · 🧸 ${overview.kindergartenCount} ta bog'cha</p>
      <div class="table-wrap"><table class="org-table">
        <thead><tr><th>Tashkilot</th><th>Turi</th><th>Jami</th><th>Nazoratda</th><th>Muddati o'tgan</th><th>Yopilgan</th><th>Ma'lumot kutilmoqda</th><th>Bajarildi</th></tr></thead>
        <tbody>${overview.perOrg
          .map(
            (o) => `<tr>
              <td>${esc(o.name)}</td>
              <td>${o.type === 'school' ? 'Maktab' : "Bog'cha"}</td>
              <td>${o.total}</td>
              <td>${o.controlPending}</td>
              <td>${o.overdue ? `<span class="badge overdue">${o.overdue}</span>` : 0}</td>
              <td>${o.controlClosed}</td>
              <td>${o.infoPending}</td>
              <td>${o.infoDone}</td>
            </tr>`
          )
          .join('')}</tbody>
      </table></div>
    `;
  }

  // ---------- Storage / cleanup tab ----------
  function formatBytes(bytes) {
    if (!bytes) return '0 MB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  async function renderStorageTab() {
    const content = document.getElementById('tab-content');
    content.innerHTML = `<div class="empty-state">Yuklanmoqda...</div>`;
    const storage = await App.api('/api/admin/storage');
    content.innerHTML = `
      <div class="stat-grid">
        <div class="stat-tile accent-primary"><div class="num">${storage.fileCount}</div><div class="label">Jami fayllar</div></div>
        <div class="stat-tile accent-primary"><div class="num">${formatBytes(storage.totalSizeBytes)}</div><div class="label">Egallagan hajm</div></div>
        <div class="stat-tile accent-warning"><div class="num">${storage.cleanupEligibleCount}</div><div class="label">Tozalash mumkin (90+ kun, yakunlangan)</div></div>
        <div class="stat-tile accent-warning"><div class="num">${formatBytes(storage.cleanupEligibleSizeBytes)}</div><div class="label">Bo'shaydigan joy</div></div>
      </div>
      <div class="card card-pad">
        <div class="section-title" style="margin-top:0">Eski fayllarni tozalash</div>
        <p class="hint muted">
          Faqat <b>to'liq yakunlangan</b> (barcha tashkilotlarda nazoratdan yechilgan yoki bajarilgan)
          topshiriqlarning fayllari o'chiriladi. Hali kutilayotgan (faol) topshiriqlarning fayllariga tegilmaydi.
          Topshiriqning o'zi (matni, tarixi) saqlanib qoladi — faqat biriktirilgan fayllar o'chiriladi.
        </p>
        <div class="field" style="max-width:220px">
          <label>Necha kundan eski</label>
          <input type="number" id="f-cleanup-days" value="90" min="0" />
        </div>
        <button class="btn danger" id="btn-cleanup">🗑️ Fayllarni tozalash</button>
      </div>
    `;

    document.getElementById('btn-cleanup').onclick = async () => {
      const days = Number(document.getElementById('f-cleanup-days').value) || 0;
      if (!confirm(`${days} kundan eski, yakunlangan topshiriqlarning fayllari butunlay o'chiriladi. Davom etasizmi?`)) return;
      try {
        const result = await App.api('/api/admin/cleanup-files', { method: 'POST', body: { olderThanDays: days } });
        App.toast(`${result.deletedCount} ta fayl o'chirildi, ${formatBytes(result.freedBytes)} bo'shadi ✅`);
        renderStorageTab();
      } catch (err) {
        App.toast(err.message);
      }
    };
  }

  // ---------- shell ----------
  function setTab(tab) {
    document.querySelectorAll('.tabs .tab-btn').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
    if (tab === 'users') renderUsersTab();
    else if (tab === 'orgs') renderOrgsTab();
    else if (tab === 'storage') renderStorageTab();
    else renderStatsTab();
  }

  document.querySelectorAll('.tabs .tab-btn').forEach((b) => b.addEventListener('click', () => setTab(b.dataset.tab)));
  document.getElementById('btn-logout').onclick = async () => {
    await App.api('/api/auth/logout', { method: 'POST' });
    location.href = '/admin/login';
  };

  (async function init() {
    try {
      const { user } = await App.api('/api/auth/me');
      if (user.role !== 'admin') {
        location.href = '/';
        return;
      }
    } catch {
      location.href = '/admin/login';
      return;
    }
    setTab('users');
  })();
})();
