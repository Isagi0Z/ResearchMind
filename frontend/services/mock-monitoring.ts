import { MonitoringSnapshot, ModuleHealth, PerformanceMetric, QueueJob, ErrorEvent, HealthStatus } from '@/types/monitoring';

function crc32(str: string): string {
  let crc = 0 ^ (-1);
  for (let i = 0; i < str.length; i++) {
    let byte = str.charCodeAt(i);
    crc = crc ^ byte;
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
  }
  return ((crc ^ (-1)) >>> 0).toString(16).padStart(8, '0');
}

class LCG {
  private seed: number;
  constructor(seedStr: string) {
    this.seed = parseInt(crc32(seedStr), 16) || 12345;
  }
  next(): number {
    this.seed = (this.seed * 1664525 + 1013904223) % 4294967296;
    return this.seed / 4294967296;
  }
  nextInt(min: number, max: number): number {
    return Math.floor(this.next() * (max - min + 1)) + min;
  }
  nextElement<T>(arr: T[]): T {
    return arr[this.nextInt(0, arr.length - 1)];
  }
}

const MODULES = [
  { id: 'm1', name: 'M1 Extraction Engine' },
  { id: 'm2', name: 'M2 Entity Resolution' },
  { id: 'm3', name: 'M3 Corpus Graph' },
  { id: 'm4', name: 'M4 Reasoning Engine' },
  { id: 'm5', name: 'M5 Query System' },
  { id: 'm6', name: 'M6 Synthesis Engine' }
];

const ERROR_MESSAGES = [
  "Timeout establishing graph connection",
  "Entity resolution conflict detected",
  "Malformed PDF extraction attempt",
  "Synthesis token limit exceeded",
  "Worker thread crash"
];

export function generateMockMonitoring(timeRangeStr: string): MonitoringSnapshot {
  const rng = new LCG(`monitoring-${timeRangeStr}`);

  const health: ModuleHealth[] = MODULES.map(m => {
    const statVal = rng.next();
    const status: HealthStatus = statVal > 0.95 ? 'Error' : (statVal > 0.8 ? 'Warning' : 'Healthy');
    return {
      moduleId: m.id,
      name: m.name,
      status,
      uptime: `${rng.nextInt(90, 99)}.${rng.nextInt(10, 99)}%`,
      activeThreads: rng.nextInt(1, 24)
    };
  });

  const charts: PerformanceMetric[] = [];
  for (let i = 0; i < 24; i++) {
    charts.push({
      label: `T-${24 - i}h`,
      throughput: rng.nextInt(100, 5000),
      latencyMs: rng.nextInt(20, 800),
      successRate: Number((rng.next() * 0.1 + 0.9).toFixed(3)) // 90-100%
    });
  }

  const queue: QueueJob[] = [];
  const queueSize = rng.nextInt(20, 100);
  for (let i = 0; i < queueSize; i++) {
    queue.push({
      id: crc32(`job-${i}-${timeRangeStr}`),
      moduleId: rng.nextElement(MODULES).id,
      type: rng.nextElement(['Extraction', 'Resolution', 'Query', 'Synthesis']),
      status: rng.nextElement(['active', 'pending', 'completed', 'failed', 'completed']),
      submitTimeStr: `T-${rng.nextInt(1, 60)}m`,
      durationMs: rng.nextInt(500, 15000)
    });
  }

  const recentErrors: ErrorEvent[] = [];
  const errSize = rng.nextInt(5, 15);
  for (let i = 0; i < errSize; i++) {
    recentErrors.push({
      id: crc32(`err-${i}-${timeRangeStr}`),
      moduleId: rng.nextElement(MODULES).id,
      type: 'RUNTIME_EXCEPTION',
      severity: rng.nextElement(['low', 'medium', 'high', 'critical']),
      message: rng.nextElement(ERROR_MESSAGES),
      timeStr: `T-${rng.nextInt(1, 120)}m`
    });
  }

  return {
    id: crc32(timeRangeStr),
    health,
    metrics: {
      documentsProcessed: rng.nextInt(50000, 150000),
      entitiesResolved: rng.nextInt(200000, 800000),
      graphNodes: 284050, // Static deterministic large number
      graphEdges: 1400230,
      queriesExecuted: rng.nextInt(1000, 10000),
      reviewsGenerated: rng.nextInt(100, 500)
    },
    charts,
    queue,
    recentErrors,
    corpus: {
      documentCount: 52000,
      authorCount: 18450,
      entityCount: 284050,
      reviewCount: 412
    }
  };
}
