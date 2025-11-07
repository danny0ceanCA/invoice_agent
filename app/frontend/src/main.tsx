import React from "react";
import ReactDOM from "react-dom/client";
import { Auth0Provider } from "@auth0/auth0-react";
import { BrowserRouter } from "react-router-dom";

import { App } from "./pages/App";

import "./styles/global.css";

const domain = import.meta.env.VITE_AUTH0_DOMAIN;
const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID;
const audience = import.meta.env.VITE_AUTH0_AUDIENCE;

if (!domain || !clientId) {
  throw new Error("Auth0 configuration is missing. Please define VITE_AUTH0_DOMAIN and VITE_AUTH0_CLIENT_ID.");
}

const authorizationParams = {
  scope: "openid profile email read:profile read:email",
  ...(audience ? { audience } : {}),
};

const redirectUri = window.location.origin;

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      authorizationParams={authorizationParams}
      redirectUri={redirectUri}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Auth0Provider>
  </React.StrictMode>
);
