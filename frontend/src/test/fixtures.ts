import type { Catalog, DemoTransfer } from '../api'

export function transfer(number: number, outcome: 'CLEAN' | 'INVESTIGATION_REQUIRED' = 'CLEAN'): DemoTransfer {
  const id = `TRF-${number}` as DemoTransfer['transferId']
  const unresolved = outcome === 'INVESTIGATION_REQUIRED' ? 1 : 0
  return {
    transferId: id,
    title: number === 1002 ? 'Split timing and unexplained quantity mismatch' : 'Matching positions',
    clientName: number === 1001 ? 'Avery DemoVale' : 'Morgan DemoReed',
    deliveringFirmName: 'Summit Wealth',
    receivingFirmName: 'Northstar Securities',
    sourceAccountReference: `FICTIONAL-SRC-${number}`,
    destinationAccountReference: `FICTIONAL-DST-${number}`,
    transferType: 'FULL',
    transferStatus: 'DRAFT',
    lastUpdated: '2026-08-15T12:00:00Z',
    evidenceMode: 'PRECOMPUTED_SYNTHETIC_SAMPLE',
    liveExecution: false,
    reconciliationRunId: null,
    ruleVersion: 'reconciliation-1',
    totalPositions: 1,
    directlyMatched: unresolved ? 0 : 1,
    evidenceExplained: 0,
    unresolvedCount: unresolved,
    costBasisIssues: 0,
    expectedWorkflowOutcome: outcome,
    requiresCostBasisReview: false,
    quantityReconciliationOnly: true,
    positions: [{
      securityId: number === 1002 ? 'SEC-104' : 'SEC-001',
      classification: unresolved ? 'UNRESOLVED' : 'MATCHED',
      sourceQuantity: unresolved ? '120' : '100',
      targetQuantity: '100',
      expectedQuantity: unresolved ? '120' : '100',
      difference: unresolved ? '-20' : '0',
    }],
    exceptions: unresolved ? [{
      securityId: 'SEC-104', exceptionType: 'QUANTITY_MISMATCH', resolutionStatus: 'UNRESOLVED',
      description: 'Receiving minus expected quantity differs.',
    }] : [],
  }
}

export function catalog(): Catalog {
  return {
    fictionalDemo: true,
    readOnly: true,
    evidenceMode: 'PRECOMPUTED_SYNTHETIC_SAMPLE',
    notice: 'Fictional read-only samples.',
    items: [transfer(1001), transfer(1002, 'INVESTIGATION_REQUIRED'), transfer(1003), transfer(1004), transfer(1005, 'INVESTIGATION_REQUIRED')],
  }
}
