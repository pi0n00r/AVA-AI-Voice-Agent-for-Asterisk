// @vitest-environment jsdom
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import HelpTooltip from './HelpTooltip';
import { Modal } from './Modal';

afterEach(() => vi.restoreAllMocks());

it('keeps the right edge inside the scrolling pane, including its scrollbar gutter', () => {
    const { container } = render(
        <div style={{ overflowX: 'auto' }}><HelpTooltip content="Keyterm instructions" /></div>
    );
    const pane = container.firstElementChild as HTMLElement;
    const trigger = screen.getByRole('button');
    vi.spyOn(pane, 'getBoundingClientRect').mockReturnValue(new DOMRect(300, 100, 460, 400));
    vi.spyOn(pane, 'clientWidth', 'get').mockReturnValue(440);
    vi.spyOn(trigger, 'getBoundingClientRect').mockReturnValue(new DOMRect(700, 250, 16, 16));
    vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockReturnValue(256);

    fireEvent.focus(trigger);

    const tooltip = screen.getByRole('tooltip');
    const right = 700 + parseFloat(tooltip.style.left) + tooltip.offsetWidth;
    expect(right).toBe(300 + pane.clientWidth - 8);
});

it('restores trigger focus on Escape from the link without closing the dialog', () => {
    const onClose = vi.fn();
    render(
        <Modal isOpen onClose={onClose} title="Provider settings">
            <HelpTooltip content="Voice settings" link="https://example.com/help" />
        </Modal>
    );
    const trigger = screen.getByRole('button', { name: 'Show help' });
    act(() => trigger.focus());
    const link = screen.getByRole('link');
    act(() => link.focus());
    expect(document.activeElement).toBe(link);
    fireEvent.keyDown(link, { key: 'Escape' });

    expect(screen.queryByRole('tooltip')).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.keyDown(trigger, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
});
