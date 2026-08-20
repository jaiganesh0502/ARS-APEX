import { AxiosError } from 'axios';
import { describe, expect, it } from 'vitest';

import { shouldLogApiError } from './client';

describe('API error logging', () => {
  it('does not report an expected missing optional resource as a console error', () => {
    const error = {
      config: { suppressErrorLog: true },
      response: { status: 404 },
    } as AxiosError;

    expect(shouldLogApiError(error)).toBe(false);
  });

  it('continues reporting unexpected API failures', () => {
    const error = {
      config: {},
      response: { status: 500 },
    } as AxiosError;

    expect(shouldLogApiError(error)).toBe(true);
  });
});
