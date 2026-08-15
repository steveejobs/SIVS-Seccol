(function initializeHttp(global) {
  const core = global.SIVSCore ||= {};

  core.createApiClient = function createApiClient({ getCsrf, onUnauthorized }) {
    return async function api(url, options = {}) {
      const headers = { ...(options.headers || {}) };
      if (options.body && !(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
      const csrf = getCsrf?.();
      if (csrf && options.method && options.method !== "GET") headers["X-CSRF-Token"] = csrf;

      const response = await fetch(url, { credentials: "same-origin", ...options, headers });
      let data;
      try {
        data = await response.json();
      } catch {
        data = { ok: false, message: "Resposta inválida do servidor" };
      }

      if (!response.ok) {
        if (response.status === 401) onUnauthorized?.();
        const failure = new Error(data.message || "Não foi possível concluir a operação");
        failure.code = data.error;
        failure.requestId = data.requestId;
        throw failure;
      }
      return data;
    };
  };
})(window);
