(function () {
  window.App = window.App || {};

  App.toast = function (message) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  };

  App.api = async function (path, options = {}) {
    const res = await fetch(path, {
      credentials: 'include',
      headers: options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : undefined,
      ...options,
      body: options.body && !(options.body instanceof FormData) ? JSON.stringify(options.body) : options.body,
    });
    let data = null;
    try {
      data = await res.json();
    } catch {
      // no body
    }
    if (!res.ok) {
      const error = new Error(data?.error || `So'rov xatosi (${res.status})`);
      error.status = res.status;
      throw error;
    }
    return data;
  };

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch((err) => console.error('SW register failed', err));
    });
  }

  let deferredInstallPrompt = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    document.dispatchEvent(new CustomEvent('pwa-install-available'));
  });

  App.canInstall = () => Boolean(deferredInstallPrompt);
  App.promptInstall = async () => {
    if (!deferredInstallPrompt) return false;
    deferredInstallPrompt.prompt();
    const choice = await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    return choice.outcome === 'accepted';
  };

  window.addEventListener('appinstalled', () => {
    deferredInstallPrompt = null;
    App.toast("Ilova o'rnatildi ✅");
  });

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = atob(base64);
    return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
  }

  App.enablePushNotifications = async function () {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      App.toast('Brauzeringiz push bildirishnomalarni qo\'llab-quvvatlamaydi');
      return false;
    }
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      App.toast('Bildirishnomalarga ruxsat berilmadi');
      return false;
    }
    try {
      const { publicKey, configured } = await App.api('/api/push/public-key');
      if (!configured) {
        App.toast('Bildirishnoma xizmati hali sozlanmagan');
        return false;
      }
      const reg = await navigator.serviceWorker.ready;
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey),
        });
      }
      await App.api('/api/push/subscribe', { method: 'POST', body: { subscription: sub.toJSON() } });
      App.toast('Bildirishnomalar yoqildi ✅');
      return true;
    } catch (err) {
      console.error(err);
      App.toast('Bildirishnomani yoqib bo\'lmadi');
      return false;
    }
  };
})();
