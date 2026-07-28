/**
 * Barrel export for the QuestionComposer feature.
 *
 * Public surface:
 *   - types + constants (re-exported)
 *   - useGenerate (the state machine)
 *   - presentation components (GenerateHero, GenerateControls,
 *     GenerateResultsHeader, ScoreCard, GenerateEmptyState, QuestionCard,
 *     ExplanationPanel)
 */
export * from './types';
export * from './constants';

export { useGenerate } from './useGenerate';

export { GenerateHero } from './GenerateHero';
export { GenerateControls } from './GenerateControls';
export {
  GenerateResultsHeader,
  ScoreCard,
} from './GenerateResultsHeader';
export { GenerateEmptyState } from './GenerateEmptyState';
export { QuestionCard } from './QuestionCard';
export { ExplanationPanel, ExplanationBlock } from './ExplanationPanel';