export type StepRevisionAction = 'poll' | 'load' | 'stop';

export function isStepFileName(fileName: string) {
  return /\.(step|stp)$/i.test(fileName);
}

export function revisionAction(
  status: Api.Cad.ParseStatusValue | undefined,
  requestFailed = false
): StepRevisionAction {
  if (requestFailed) return 'stop';
  if (status === 'completed') return 'load';
  if (status === 'uploaded' || status === 'queued' || status === 'processing') return 'poll';
  return 'stop';
}

export function shouldLockStepView(annotationCount: number) {
  return annotationCount > 0;
}
