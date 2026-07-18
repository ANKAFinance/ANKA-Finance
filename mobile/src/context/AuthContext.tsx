import * as SecureStore from "expo-secure-store";
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api, setToken, User } from "../api/client";

const TOKEN_KEY = "finance_tracker_token";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string, currency?: string) => Promise<void>;
  signOut: () => Promise<void>;
  deleteAccount: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const token = await SecureStore.getItemAsync(TOKEN_KEY);
      if (!token) {
        setLoading(false);
        return;
      }
      setToken(token);
      try {
        const { user: me } = await api.me();
        setUser(me);
      } catch {
        await SecureStore.deleteItemAsync(TOKEN_KEY);
        setToken(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      signIn: async (email, password) => {
        const { token, user: signedIn } = await api.login({ email, password });
        await SecureStore.setItemAsync(TOKEN_KEY, token);
        setToken(token);
        setUser(signedIn);
      },
      signUp: async (name, email, password, currency = "USD") => {
        const { token, user: registered } = await api.register({ name, email, password, currency });
        await SecureStore.setItemAsync(TOKEN_KEY, token);
        setToken(token);
        setUser(registered);
      },
      signOut: async () => {
        await SecureStore.deleteItemAsync(TOKEN_KEY);
        setToken(null);
        setUser(null);
      },
      deleteAccount: async () => {
        await api.deleteMe();
        await SecureStore.deleteItemAsync(TOKEN_KEY);
        setToken(null);
        setUser(null);
      },
      refreshUser: async () => {
        const { user: me } = await api.me();
        setUser(me);
      },
    }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
