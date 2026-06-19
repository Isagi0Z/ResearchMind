"use client";

import React from "react";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const errorId = `err-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;

      return (
        <div className="flex flex-col items-center justify-center p-8 text-center min-h-[300px] border rounded-lg bg-background">
          <AlertCircle className="w-10 h-10 text-destructive mb-4" />
          <h3 className="text-lg font-semibold">Something went wrong</h3>
          <p className="text-muted-foreground mt-2 mb-4 max-w-sm">
            An unexpected error occurred. Please try again.
          </p>
          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={this.handleRetry}>
              Try Again
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-4">
            Reference: {errorId}
          </p>
        </div>
      );
    }

    return this.props.children;
  }
}
