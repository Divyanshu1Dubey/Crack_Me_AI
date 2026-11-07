/**
 * Barrel export for the QuestionComposer feature.
 *
 * Public surface:
 *   - types + constants + limits (batch size per plan) (re-exported)
 *   - useGenerate (the state machine), useGenerationLimit (the user's batch limit)
 *   - presentation components (GenerateHero, GenerateControls,
 *     GenerateResultsHeader, ScoreCard, GenerateEmptyState, QuestionCard,
 *     ExplanationPanel)
 */
export * from './types';
export * from './constants';
export * from './limits';

export { useGenerate } from './useGenerate';
export { useGenerationLimit } from './useGenerationLimit';

export { GenerateHero } from './GenerateHero';
export { GenerateControls } from './GenerateControls';
export {
  GenerateResultsHeader,
  ScoreCard,
} from './GenerateResultsHeader';
export { GenerateEmptyState } from './GenerateEmptyState';
export { QuestionCard } from './QuestionCard';
export { ExplanationPanel, ExplanationBlock } from './ExplanationPanel';