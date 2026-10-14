/*
 * InstaTool WebExtension API shim.
 *
 * This file is an expression that evaluates to a factory: factory(config) -> chrome namespace.
 * ExtensionManager embeds it in every content-script wrapper and serves it to extension pages
 * (background, popup, options). All privileged calls are posted as JSON over the WebView
 * message bridge named config.bridge and answered by Kotlin.
 *
 * Content scripts run in the page's main world (WebView has no isolated worlds), so the shim
 * keeps its state in closures and only installs `chrome`/`browser` globals in extension pages.
 */
(function (cfg) {
  'use strict';

  var stringify = JSON.stringify;
  var parse = JSON.parse;
  var IID = Math.random().toString(36).slice(2) + Date.now().toString(36);
  var MAX_CONNECT_ATTEMPTS = 100;

  var bridge = null;
  var seq = 0;
  var pending = {};
  var outbox = [];
  var flushTimer = null;
  var connectAttempts = 0;

  function connect() {
    if (bridge) return bridge;
    var candidate = globalThis[cfg.bridge];
    if (candidate && typeof candidate.postMessage === 'function') {
      bridge = candidate;
      bridge.addEventListener('message', onBridgeMessage);
    }
    return bridge;
  }

  function flush() {
    flushTimer = null;
    if (!connect()) {
      if (++connectAttempts > MAX_CONNECT_ATTEMPTS) {
        outbox = [];
        Object.keys(pending).forEach(function (id) {
          pending[id].reject(new Error('Extension bridge unavailable'));
          delete pending[id];
        });
        return;
      }
      flushTimer = setTimeout(flush, 50);
      return;
    }
    while (outbox.length) bridge.postMessage(outbox.shift());
  }

  function post(message) {
    message.ext = cfg.id;
    message.iid = IID;
    message.url = location.href;
    outbox.push(stringify(message));
    if (connect()) flush();
    else if (!flushTimer) flushTimer = setTimeout(flush, 0);
  }

  function request(type, payload) {
    return new Promise(function (resolve, reject) {
      var id = ++seq;
      pending[id] = { resolve: resolve, reject: reject };
      post({ id: id, type: type, payload: payload === undefined ? null : payload });
    });
  }

  function onBridgeMessage(event) {
    var message;
    try {
      message = typeof event.data === 'string' ? parse(event.data) : event.data;
    } catch (e) {
      return;
    }
    if (!message || message.ext !== cfg.id) return;
    if (message.id) {
      if (message.iid !== IID) return;
      var waiter = pending[message.id];
      if (!waiter) return;
      delete pending[message.id];
      if (message.error !== undefined) waiter.reject(new Error(message.error));
      else waiter.resolve(message.result);
      return;
    }
    if (message.event) handleEvent(message);
  }

  function makeEvent() {
    var listeners = [];
    return {
      addListener: function (fn) {
        if (typeof fn === 'function' && listeners.indexOf(fn) < 0) listeners.push(fn);
      },
      removeListener: function (fn) {
        var i = listeners.indexOf(fn);
        if (i >= 0) listeners.splice(i, 1);
      },
      hasListener: function (fn) { return listeners.indexOf(fn) >= 0; },
      hasListeners: function () { return listeners.length > 0; },
      _listeners: function () { return listeners.slice(); },
      _dispatch: function () {
        var args = arguments;
        listeners.slice().forEach(function (fn) {
          try { fn.apply(null, args); } catch (e) { console.error(e); }
        });
      }
    };
  }

  function noop() {}

  /** Chrome-style dual API: returns a Promise, or invokes the callback with runtime.lastError set on failure. */
  function api(promise, callback) {
    if (typeof callback !== 'function') return promise;
    promise.then(function (result) {
      callback(result);
    }, function (error) {
      runtime.lastError = { message: String(error && error.message || error) };
      try { callback(); } finally { runtime.lastError = undefined; }
    });
  }

  function resolved(value, callback) {
    return api(Promise.resolve(value), callback);
  }

  // ---------------------------------------------------------------- runtime

  var runtime = {
    id: cfg.id,
    lastError: undefined,
    getURL: function (path) {
      path = String(path == null ? '' : path);
      if (path.charAt(0) === '/') path = path.slice(1);
      return cfg.baseUrl + path;
    },
    getManifest: function () { return parse(stringify(cfg.manifest)); },
    sendMessage: function () {
      var args = Array.prototype.slice.call(arguments);
      var callback = typeof args[args.length - 1] === 'function' ? args.pop() : undefined;
      var extensionId = null;
      var message;
      if (args.length >= 3 || (args.length === 2 && (typeof args[0] === 'string' || args[0] == null) &&
          !(args[1] && typeof args[1] === 'object' && 'includeTlsChannelId' in args[1]))) {
        extensionId = args[0];
        message = args[1];
      } else {
        message = args[0];
      }
      if (extensionId && extensionId !== cfg.id) {
        return api(Promise.reject(new Error('Messaging other extensions is not supported')), callback);
      }
      return api(request('runtime.sendMessage', { message: message === undefined ? null : message }), callback);
    },
    connect: function () {
      var port = {
        name: '', sender: undefined,
        onMessage: makeEvent(), onDisconnect: makeEvent(),
        postMessage: function () { console.warn('runtime.connect ports are not supported'); },
        disconnect: noop
      };
      setTimeout(function () { port.onDisconnect._dispatch(port); }, 0);
      return port;
    },
    getPlatformInfo: function (callback) {
      return resolved({ os: 'android', arch: 'arm64', nacl_arch: 'arm' }, callback);
    },
    openOptionsPage: function (callback) { return api(request('runtime.openOptionsPage'), callback); },
    setUninstallURL: function (url, callback) { return resolved(undefined, callback); },
    reload: function () { request('runtime.reload'); },
    onMessage: makeEvent(),
    onMessageExternal: makeEvent(),
    onConnect: makeEvent(),
    onConnectExternal: makeEvent(),
    onInstalled: makeEvent(),
    onStartup: makeEvent(),
    onSuspend: makeEvent(),
    onUpdateAvailable: makeEvent()
  };

  /** Delivers a message to runtime.onMessage listeners; done(handled, response, hasResponse). */
  function dispatchMessage(message, sender, done) {
    var listeners = runtime.onMessage._listeners();
    if (!listeners.length) return done(false);
    var responded = false;
    var async = false;
    function sendResponse(response) {
      if (responded) return;
      responded = true;
      done(true, response, true);
    }
    listeners.forEach(function (fn) {
      try {
        var result = fn(message, sender, sendResponse);
        if (result === true) {
          async = true;
        } else if (result && typeof result.then === 'function') {
          async = true;
          result.then(sendResponse, function (e) { console.error(e); sendResponse(undefined); });
        }
      } catch (e) {
        console.error(e);
      }
    });
    if (!async && !responded) {
      responded = true;
      done(true, undefined, false);
    }
  }

  // ---------------------------------------------------------------- storage

  function storageArea(area) {
    return {
      get: function (keys, callback) {
        if (typeof keys === 'function') { callback = keys; keys = null; }
        return api(request('storage.get', { area: area, keys: keys === undefined ? null : keys }), callback);
      },
      set: function (items, callback) {
        return api(request('storage.set', { area: area, items: items || {} }).then(noop), callback);
      },
      remove: function (keys, callback) {
        return api(request('storage.remove', { area: area, keys: keys }).then(noop), callback);
      },
      clear: function (callback) {
        return api(request('storage.clear', { area: area }).then(noop), callback);
      },
      getBytesInUse: function (keys, callback) {
        if (typeof keys === 'function') { callback = keys; keys = null; }
        return api(request('storage.getBytesInUse', { area: area, keys: keys === undefined ? null : keys }), callback);
      },
      setAccessLevel: function (options, callback) { return resolved(undefined, callback); },
      onChanged: makeEvent()
    };
  }

  var areas = {
    local: storageArea('local'),
    sync: storageArea('sync'),
    session: storageArea('session'),
    managed: storageArea('managed')
  };
  areas.local.QUOTA_BYTES = 10485760;
  areas.sync.QUOTA_BYTES = 102400;

  var storage = {
    local: areas.local,
    sync: areas.sync,
    session: areas.session,
    managed: areas.managed,
    onChanged: makeEvent()
  };

  // ---------------------------------------------------------------- i18n

  var messages = cfg.messages || {};
  var i18n = {
    getMessage: function (name, substitutions) {
      var key = String(name).toLowerCase();
      if (key === '@@extension_id') return cfg.id;
      if (key === '@@ui_locale') return (navigator.language || 'en').replace('-', '_');
      var entry = messages[key];
      if (!entry) return '';
      var subs = substitutions == null ? [] : (Array.isArray(substitutions) ? substitutions : [substitutions]);
      var placeholders = entry.placeholders || {};
      var text = String(entry.message || '').replace(/\$([a-zA-Z0-9_@]+)\$/g, function (match, placeholder) {
        var p = placeholders[placeholder.toLowerCase()];
        return p ? String(p.content) : match;
      });
      text = text.replace(/\$(\d)/g, function (match, index) {
        var value = subs[Number(index) - 1];
        return value == null ? '' : String(value);
      });
      return text.replace(/\$\$/g, '$');
    },
    getUILanguage: function () { return navigator.language || 'en'; },
    getAcceptLanguages: function (callback) { return resolved(navigator.languages ? navigator.languages.slice() : ['en'], callback); },
    detectLanguage: function (text, callback) { return resolved({ isReliable: false, languages: [] }, callback); }
  };

  var chromeApi = {
    runtime: runtime,
    storage: storage,
    i18n: i18n,
    extension: {
      getURL: runtime.getURL,
      inIncognitoContext: !!cfg.incognito,
      isAllowedIncognitoAccess: function (callback) { return resolved(true, callback); }
    }
  };

  // ------------------------------------------------- extension-page-only APIs

  if (cfg.context !== 'content') {
    var tabs = {
      TAB_ID_NONE: -1,
      create: function (props, callback) { return api(request('tabs.create', props || {}), callback); },
      query: function (query, callback) { return api(request('tabs.query', { query: query || {} }), callback); },
      get: function (tabId, callback) { return api(request('tabs.get', { tabId: tabId }), callback); },
      getCurrent: function (callback) { return resolved(undefined, callback); },
      update: function (tabId, props, callback) {
        if (typeof tabId === 'object' && tabId !== null) { callback = props; props = tabId; tabId = null; }
        return api(request('tabs.update', { tabId: tabId, props: props || {} }), callback);
      },
      remove: function (tabIds, callback) {
        return api(request('tabs.remove', { tabIds: Array.isArray(tabIds) ? tabIds : [tabIds] }).then(noop), callback);
      },
      reload: function (tabId, props, callback) {
        if (typeof tabId === 'function') { callback = tabId; tabId = null; }
        if (typeof props === 'function') { callback = props; }
        return api(request('tabs.reload', { tabId: typeof tabId === 'number' ? tabId : null }).then(noop), callback);
      },
      sendMessage: function (tabId, message, options, callback) {
        if (typeof options === 'function') { callback = options; options = {}; }
        var payload = { tabId: tabId, message: message === undefined ? null : message };
        if (options && typeof options.frameId === 'number') payload.frameId = options.frameId;
        return api(request('tabs.sendMessage', payload), callback);
      },
      onCreated: makeEvent(),
      onUpdated: makeEvent(),
      onRemoved: makeEvent(),
      onActivated: makeEvent(),
      onReplaced: makeEvent()
    };

    var windowInfo = function () { return { id: 1, focused: true, type: 'normal', state: 'normal', incognito: false, alwaysOnTop: false }; };
    var windows = {
      WINDOW_ID_NONE: -1,
      WINDOW_ID_CURRENT: -2,
      get: function (id, info, callback) { return resolved(windowInfo(), typeof info === 'function' ? info : callback); },
      getCurrent: function (info, callback) { return resolved(windowInfo(), typeof info === 'function' ? info : callback); },
      getLastFocused: function (info, callback) { return resolved(windowInfo(), typeof info === 'function' ? info : callback); },
      getAll: function (info, callback) { return resolved([windowInfo()], typeof info === 'function' ? info : callback); },
      create: function (data, callback) {
        var url = data && data.url;
        if (Array.isArray(url)) url = url[0];
        return api(request('tabs.create', { url: url }).then(function () { return windowInfo(); }), callback);
      },
      onCreated: makeEvent(),
      onRemoved: makeEvent(),
      onFocusChanged: makeEvent()
    };

    var action = {};
    ['setBadgeText', 'setBadgeBackgroundColor', 'setBadgeTextColor', 'setIcon', 'setTitle', 'setPopup', 'enable', 'disable', 'show', 'hide']
      .forEach(function (name) {
        action[name] = function () {
          var callback = arguments[arguments.length - 1];
          return resolved(undefined, typeof callback === 'function' ? callback : undefined);
        };
      });
    action.getBadgeText = function (details, callback) { return resolved('', callback); };
    action.getTitle = function (details, callback) { return resolved(cfg.manifest.name || '', callback); };
    action.getPopup = function (details, callback) { return resolved('', callback); };
    action.onClicked = makeEvent();

    var alarms = (function () {
      var timers = {};
      var info = {};
      var onAlarm = makeEvent();
      function clear(name) {
        name = name || '';
        if (!(name in info)) return false;
        clearTimeout(timers[name]);
        clearInterval(timers[name]);
        delete timers[name];
        delete info[name];
        return true;
      }
      return {
        create: function (name, options, callback) {
          if (typeof name === 'object' && name !== null) { callback = options; options = name; name = ''; }
          name = name || '';
          options = options || {};
          clear(name);
          var delay = options.when ? Math.max(0, options.when - Date.now())
            : (options.delayInMinutes != null ? options.delayInMinutes : (options.periodInMinutes || 0)) * 60000;
          var period = options.periodInMinutes ? options.periodInMinutes * 60000 : 0;
          var alarm = info[name] = { name: name, scheduledTime: Date.now() + delay, periodInMinutes: options.periodInMinutes };
          var fire = function () {
            alarm.scheduledTime = Date.now() + period;
            onAlarm._dispatch(Object.assign({}, alarm));
            if (!period) { delete info[name]; delete timers[name]; }
          };
          timers[name] = setTimeout(function () {
            fire();
            if (period) timers[name] = setInterval(fire, period);
          }, delay);
          return resolved(undefined, callback);
        },
        get: function (name, callback) {
          if (typeof name === 'function') { callback = name; name = ''; }
          return resolved(info[name || ''] ? Object.assign({}, info[name || '']) : undefined, callback);
        },
        getAll: function (callback) {
          return resolved(Object.keys(info).map(function (k) { return Object.assign({}, info[k]); }), callback);
        },
        clear: function (name, callback) {
          if (typeof name === 'function') { callback = name; name = ''; }
          return resolved(clear(name), callback);
        },
        clearAll: function (callback) {
          var had = Object.keys(info).length > 0;
          Object.keys(info).forEach(clear);
          return resolved(had, callback);
        },
        onAlarm: onAlarm
      };
    })();

    var declarativeNetRequest = {
      MAX_NUMBER_OF_DYNAMIC_RULES: 5000,
      getEnabledRulesets: function (callback) { return api(request('dnr.getEnabledRulesets'), callback); },
      updateEnabledRulesets: function (options, callback) { return api(request('dnr.updateEnabledRulesets', options || {}).then(noop), callback); },
      getDynamicRules: function (filter, callback) {
        if (typeof filter === 'function') callback = filter;
        return api(request('dnr.getRules', { kind: 'dynamic' }), callback);
      },
      updateDynamicRules: function (options, callback) {
        return api(request('dnr.updateRules', Object.assign({ kind: 'dynamic' }, options || {})).then(noop), callback);
      },
      getSessionRules: function (filter, callback) {
        if (typeof filter === 'function') callback = filter;
        return api(request('dnr.getRules', { kind: 'session' }), callback);
      },
      updateSessionRules: function (options, callback) {
        return api(request('dnr.updateRules', Object.assign({ kind: 'session' }, options || {})).then(noop), callback);
      },
      isRegexSupported: function (options, callback) { return resolved({ isSupported: true }, callback); },
      onRuleMatchedDebug: makeEvent()
    };

    var permissions = {
      contains: function (perms, callback) { return resolved(true, callback); },
      request: function (perms, callback) { return resolved(true, callback); },
      remove: function (perms, callback) { return resolved(true, callback); },
      getAll: function (callback) {
        return resolved({
          permissions: (cfg.manifest.permissions || []).slice(),
          origins: (cfg.manifest.host_permissions || []).slice()
        }, callback);
      },
      onAdded: makeEvent(),
      onRemoved: makeEvent()
    };

    var contextMenus = {
      create: function (props, callback) {
        if (typeof callback === 'function') setTimeout(callback, 0);
        return props && props.id;
      },
      update: function () { var cb = arguments[arguments.length - 1]; return resolved(undefined, typeof cb === 'function' ? cb : undefined); },
      remove: function (id, callback) { return resolved(undefined, callback); },
      removeAll: function (callback) { return resolved(undefined, callback); },
      onClicked: makeEvent()
    };

    chromeApi.tabs = tabs;
    chromeApi.windows = windows;
    chromeApi.action = action;
    chromeApi.browserAction = action;
    chromeApi.pageAction = action;
    chromeApi.alarms = alarms;
    chromeApi.declarativeNetRequest = declarativeNetRequest;
    chromeApi.permissions = permissions;
    chromeApi.contextMenus = contextMenus;
    chromeApi.extension.getBackgroundPage = function () { return null; };
    chromeApi.extension.getViews = function () { return []; };

    if (cfg.context === 'background' && typeof globalThis.importScripts !== 'function') {
      // MV3 service workers may call importScripts(); emulate it with synchronous loads.
      globalThis.importScripts = function () {
        Array.prototype.slice.call(arguments).forEach(function (url) {
          var xhr = new XMLHttpRequest();
          xhr.open('GET', new URL(url, cfg.baseUrl).href, false);
          xhr.send();
          (0, eval)(xhr.responseText + '\n//# sourceURL=' + url);
        });
      };
    }

    try {
      Object.defineProperty(globalThis, 'chrome', { value: chromeApi, configurable: true, writable: true });
      Object.defineProperty(globalThis, 'browser', { value: chromeApi, configurable: true, writable: true });
    } catch (e) {
      console.error('Unable to install extension APIs', e);
    }
  }

  // ---------------------------------------------------------------- events from Kotlin

  function handleEvent(message) {
    switch (message.event) {
      case 'storage.changed':
        var area = areas[message.area];
        if (area) area.onChanged._dispatch(message.changes);
        storage.onChanged._dispatch(message.changes, message.area);
        break;
      case 'runtime.message':
        dispatchMessage(message.message, message.sender, function (handled, response, hasResponse) {
          var payload = { msgId: message.msgId, handled: handled };
          if (hasResponse && response !== undefined) payload.response = response;
          post({ type: 'runtime.respond', payload: payload });
        });
        break;
      case 'runtime.installed':
        runtime.onInstalled._dispatch(message.details);
        break;
      case 'runtime.startup':
        runtime.onStartup._dispatch();
        break;
    }
  }

  post({ type: 'hello' });
  addEventListener('pagehide', function () { post({ type: 'bye' }); });
  addEventListener('pageshow', function (event) { if (event.persisted) post({ type: 'hello' }); });
  return chromeApi;
})
