"use client";

import { AlertTriangle, ShieldAlert, Clock, Server } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface RouteErrorProps {
  status?: number;
  message?: string;
  onRetry?: () => void;
}

const ERROR_CONFIG: Record<number, { icon: React.ReactNode; title: string; description: string }> = {
  401: {
    icon: <ShieldAlert className="w-10 h-10 text-destructive mb-4" />,
    title: "Session Expired",
    description: "Your session has expired. Please log in again to continue.",
  },
  403: {
    icon: <ShieldAlert className="w-10 h-10 text-destructive mb-4" />,
    title: "Access Denied",
    description: "You do not have permission to access this resource.",
  },
  404: {
    icon: <AlertTriangle className="w-10 h-10 text-destructive mb-4" />,
    title: "Not Found",
    description: "The requested resource could not be found.",
  },
  429: {
    icon: <Clock className="w-10 h-10 text-destructive mb-4" />,
    title: "Rate Limit Exceeded",
    description: "Too many requests. Please wait a moment and try again.",
  },
};

export function RouteError({ status, message, onRetry }: RouteErrorProps) {
  const router = useRouter();
  const config = status ? ERROR_CONFIG[status] : undefined;
  const title = config?.title || "Something went wrong";
  const description = message || config?.description || "An unexpected error occurred. Please try again.";

  return (
    <div className="flex flex-col items-center justify-center p-8 text-center min-h-[400px] border rounded-lg bg-background">
      {status === 500 ? (
        <Server className="w-10 h-10 text-destructive mb-4" />
      ) : (
        config?.icon || <AlertTriangle className="w-10 h-10 text-destructive mb-4" />
      )}
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-muted-foreground mt-2 mb-6 max-w-sm">{description}</p>
      <div className="flex items-center gap-3">
        {onRetry && (
          <Button variant="outline" onClick={onRetry}>
            Try Again
          </Button>
        )}
        {(status === 401) && (
          <Button asChild>
            <Link href="/login">Log In</Link>
          </Button>
        )}
        <Button variant="ghost" onClick={() => router.back()}>
          Go Back
        </Button>
      </div>
    </div>
  );
}
