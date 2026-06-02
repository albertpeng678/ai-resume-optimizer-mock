const { test, expect } = require('@playwright/test');

test.describe('Resume Scanner API', () => {

  test('POST /analyze returns SSE stream with 5 dimension events followed by done @smoke', async ({ request }) => {
    const response = await request.post('/analyze', {
      multipart: {
        pdf_file: {
          name: 'dummy.pdf',
          mimeType: 'application/pdf',
          buffer: Buffer.from('%PDF-1.4'),
        },
      },
    });
    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('text/event-stream');

    const body = await response.body();
    const text = body.toString('utf-8');
    const lines = text.split('\n').filter(l => l.startsWith('data: '));

    const events = lines.map(l => JSON.parse(l.slice(6)));
    const dimensions = events.filter(e => e.type === 'dimension');
    const doneEvent = events.find(e => e.type === 'done');

    expect(dimensions.length).toBe(5);
    expect(dimensions[0].name).toBe('experience_relevance');
    expect(dimensions[1].name).toBe('skill_fit');
    expect(dimensions[2].name).toBe('layout_structure');
    expect(dimensions[3].name).toBe('keyword_coverage');
    expect(dimensions[4].name).toBe('personal_brand');
    expect(dimensions[0]).toHaveProperty('score');
    expect(dimensions[0]).toHaveProperty('conclusion');
    expect(dimensions[0]).toHaveProperty('suggestions');
    expect(dimensions[0]).toHaveProperty('quote');
    expect(dimensions[0]).toHaveProperty('optimized');
    expect(dimensions[0]).toHaveProperty('optimization_logic');
    expect(doneEvent).toBeDefined();
  });

  test('GET /health returns status ok', async ({ request }) => {
    const resp = await request.get('/health');
    expect(resp.status()).toBe(200);
    expect(await resp.json()).toEqual({ status: 'ok' });
  });

  test('GET / returns HTML with auth screen', async ({ request }) => {
    const resp = await request.get('/');
    expect(resp.status()).toBe(200);
    const text = await resp.text();
    expect(text).toContain('<!DOCTYPE html>');
    expect(text.toLowerCase()).toContain('ai');
    expect(text.toLowerCase()).toContain('履歷');
  });

  test('DELETE /api/analyses/nonexistent returns 404', async ({ request }) => {
    const resp = await request.delete('/api/analyses/00000000-0000-0000-0000-000000000000');
    expect(resp.status()).toBe(404);
  });

  test('GET /api/analyses returns list (may be empty)', async ({ request }) => {
    const resp = await request.get('/api/analyses');
    expect(resp.status()).toBe(200);
    const list = await resp.json();
    expect(Array.isArray(list)).toBe(true);
  });
});
