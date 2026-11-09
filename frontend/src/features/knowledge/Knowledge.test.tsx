import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, test } from 'vitest';
import { SourceReference } from './shared';

test('renders untrusted excerpt content as text and links only to the internal source view', () => {
  const excerpt =
    '<img src=https://example.org/secret> [click](javascript:alert(1))';
  const { container } = render(
    <MemoryRouter>
      <ul>
        <SourceReference
          item={{
            title: 'Synthetic source',
            label: 'S1',
            rank: 1,
            document_id: 'doc',
            version_id: 'version',
            chunk_id: 'chunk',
            ordinal: 0,
            revision_number: 1,
            heading_path: ['Desk hours'],
            start_offset: 0,
            end_offset: excerpt.length,
            excerpt,
            source_url: 'https://example.org',
          }}
        />
      </ul>
    </MemoryRouter>,
  );
  expect(screen.getByText(excerpt)).toBeVisible();
  expect(container.querySelector('img')).toBeNull();
  expect(screen.getAllByRole('link')).toHaveLength(1);
  expect(
    screen.getByRole('link', { name: 'S1 · Synthetic source' }),
  ).toHaveAttribute('href', '/app/knowledge/sources/chunk');
});
