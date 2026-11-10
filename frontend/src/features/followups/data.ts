import type { components } from '../../api/schema';

export type Task = components['schemas']['TaskView'];
export const taskBase = '/app/follow-ups/tasks';
export const taskStates = [
  'open',
  'in_progress',
  'completed',
  'cancelled',
] as const;
export const ratingLabels = [
  'Very dissatisfied',
  'Dissatisfied',
  'Neither satisfied nor dissatisfied',
  'Satisfied',
  'Very satisfied',
];
