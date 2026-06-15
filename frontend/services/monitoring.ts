import { apiClient } from "@/lib/api-client";
import { MonitoringSnapshot } from "@/types/monitoring";

export async function getMonitoringData(timeRange: string): Promise<MonitoringSnapshot> {
  const queryParams = new URLSearchParams({ timeRange });
  return await apiClient.get<MonitoringSnapshot>(`/api/v1/monitoring/metrics?${queryParams.toString()}`);
}
