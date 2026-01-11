"use client";

import { useState, useEffect } from "react";
import { Library } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useCheckSetup, useLogin, useSetup } from "@/hooks/useAuth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSetup, setIsSetup] = useState(false);

  const checkSetup = useCheckSetup();
  const login = useLogin();
  const setup = useSetup();

  useEffect(() => {
    if (checkSetup.data?.setup_required) {
      setIsSetup(true);
    }
  }, [checkSetup.data]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSetup) {
      setup.mutate({ email, password });
    } else {
      login.mutate({ email, password });
    }
  };

  const isLoading = login.isPending || setup.isPending;

  return (
    <div className="min-h-screen bg-dark-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-dark-surface rounded-2xl mb-4">
            <Library className="w-8 h-8 text-article-blue" />
          </div>
          <h1 className="text-2xl font-bold text-white">Alexandria</h1>
          <p className="text-dark-muted mt-1">Your personal research library</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-dark-surface rounded-xl p-6 border border-dark-border">
          <h2 className="text-lg font-semibold text-white mb-4">
            {isSetup ? "Create your account" : "Welcome back"}
          </h2>

          {isSetup && (
            <p className="text-sm text-dark-muted mb-4">
              Set up your Alexandria account to get started.
            </p>
          )}

          <div className="space-y-4">
            <Input
              id="email"
              type="email"
              label="Email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />

            <Input
              id="password"
              type="password"
              label="Password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />

            <Button type="submit" className="w-full" loading={isLoading}>
              {isSetup ? "Create Account" : "Sign In"}
            </Button>
          </div>
        </form>

        {/* Toggle */}
        <p className="text-center mt-4 text-sm text-dark-muted">
          {isSetup ? (
            <>
              Already have an account?{" "}
              <button
                onClick={() => setIsSetup(false)}
                className="text-article-blue hover:underline"
              >
                Sign in
              </button>
            </>
          ) : checkSetup.data?.setup_required ? (
            <>
              First time?{" "}
              <button
                onClick={() => setIsSetup(true)}
                className="text-article-blue hover:underline"
              >
                Set up your account
              </button>
            </>
          ) : null}
        </p>
      </div>
    </div>
  );
}
