import React from "react";
import ReactDOM from "react-dom/client";
import { Auth0Provider } from "@auth0/auth0-react";
import { BrowserRouter } from "react-router-dom";

import { App } from "./pages/App";

import "./styles/global.css";
import "@openai/chatkit/dist/chatkit.css";

const domain = import.meta.env.VITE_AUTH0_DOMAIN;
const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID;
const audience = import.meta.env.VITE_AUTH0_AUDIENCE;

const rootElement = document.getElementById("root") as HTMLElement;

if (!domain || !clientId) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-6 text-center text-sm text-slate-600">
        <div className="max-w-md space-y-3">
          <h1 className="text-lg font-semibold text-slate-800">Configuration required</h1>
          <p>
            The application cannot start because the Auth0 configuration is missing. Please define the
            <code className="mx-1 rounded bg-slate-200 px-1 py-0.5">VITE_AUTH0_DOMAIN</code> and
            <code className="mx-1 rounded bg-slate-200 px-1 py-0.5">VITE_AUTH0_CLIENT_ID</code> environment
            variables for the frontend build.
          </p>
        </div>
      </div>
    </React.StrictMode>,
  );
  console.error("Auth0 configuration missing. Set VITE_AUTH0_DOMAIN and VITE_AUTH0_CLIENT_ID.");
} else {
  const authorizationParams = {
    ...(audience ? { audience } : {}),
    scope: "openid profile email read:profile read:email offline_access",
  };

  const redirectUri = window.location.origin;

  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <Auth0Provider
        domain={domain}
        clientId={clientId}
        authorizationParams={authorizationParams}
        cacheLocation="localstorage"
        useRefreshTokens={true}
        useRefreshTokensFallback={false}
        redirectUri={redirectUri}
      >
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </Auth0Provider>
    </React.StrictMode>,
  );
}
