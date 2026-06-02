#!/usr/bin/env python3
"""
Klat Logo Viewer
Centering the Klat ASCII logo on a full black, GitHub Dark, or default terminal background,
featuring an interactive keyboard menu, animated intro sequences, and alignment borders.
"""

import os
import sys
import time

# Enable ANSI escape sequences on Windows
def enable_ansi():
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # ENABLE_PROCESSED_OUTPUT = 0x0001
        # ENABLE_WRAP_AT_EOL_OUTPUT = 0x0002
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        # 0x0001 | 0x0002 | 0x0004 = 7
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

# ASCII Logos from src/ui.py
LOGO_DEFAULT = [
    " __  __    ",
    "/\\ \\/ /    ",
    "\\ \\  _\"-.  ",
    " \\ \\_\\ \\_\\ ",
    "  \\/_/\\/_/ ",
    "           ",
]

LOGO_LEGACY = [
    "  ██╗  ██║██║      █████╗ ████████╗",
    "  ██║ ██╔╝██║     ██╔══██╗╚══██╔══╝",
    "  █████╔╝ ██║     ███████║   ██║   ",
    "  ██╔═██╗ ██║     ██╔══██║   ██║   ",
    "  ██║  ██╗███████╗██║  ██║   ██║   ",
    "  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ",
]

LOGO_EXPERIMENTAL = [
    " __  __     __         ______     ______  ",
    "/\\ \\/ /    /\\ \\       /\\  __ \\   /\\__  _\\ ",
    "\\ \\  _\"-.  \\ \\ \\____  \\ \\  __ \\  \\/_/\\ \\/ ",
    " \\ \\_\\ \\_\\  \\ \\_____\\  \\ \\_\\ \\_\\    \\ \\_\\ ",
    "  \\/_/\\/_/   \\/_____/   \\/_/\\/_/     \\/_/ ",
    "                                          ",
]

# Standard green gradient colors line-by-line from ui.py
LOGO_COLORS = [
    "\033[38;2;0;180;80m",
    "\033[38;2;0;188;84m",
    "\033[38;2;1;196;88m",
    "\033[38;2;1;203;91m",
    "\033[38;2;2;211;95m",
    "\033[38;2;2;219;99m",
]

RESET_ALL = "\033[0m"
FG_GRAY = "\033[38;2;120;120;120m"
BOX_COLOR = "\033[38;2;0;180;80m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

def get_terminal_size():
    try:
        return os.get_terminal_size()
    except OSError:
        return (80, 24)

def display_len(text: str) -> int:
    # Count double-width characters (like the leaf emoji 🌿) as 2 columns, others as 1
    length = 0
    for char in text:
        if ord(char) > 0xffff or char == "🌿":
            length += 2
        else:
            length += 1
    return length

def colorize_horizontal_gradient(text: str) -> str:
    if not text:
        return ""
    n = len(text)
    if n == 1:
        return f"\033[38;2;0;180;80m{text}\033[39m"
    parts = []
    for j, c in enumerate(text):
        # Smooth transition from #00b450 (0, 180, 80) to #02db63 (2, 219, 99)
        r = int(0 + 2 * j / (n - 1))
        g = int(180 + 39 * j / (n - 1))
        b = int(80 + 19 * j / (n - 1))
        parts.append(f"\033[38;2;{r};{g};{b}m{c}")
    parts.append("\033[39m")
    return "".join(parts)

def build_centered_line(text_raw: str, text_colored: str, cols: int, bg_code: str) -> str:
    # Use cols - 1 to avoid line wrap / scrolling issues at the right edge
    width = cols - 1
    raw_len = display_len(text_raw)
    if raw_len >= width:
        return text_colored[:width]
    pad_left = (width - raw_len) // 2
    pad_right = width - raw_len - pad_left
    return f"{bg_code}{' ' * pad_left}{text_colored}{bg_code}{' ' * pad_right}"

def draw_screen(mode: str, bg_mode: str, cols: int, lines: int, animation_start_time: float, show_border: bool):
    # Set background escape sequence
    if bg_mode == "black":
        bg_code = "\033[48;2;0;0;0m"
    elif bg_mode == "github_dark":
        bg_code = "\033[48;2;13;17;23m"
    else:
        # Prevent setting default background attributes explicitly to preserve subpixel ClearType rendering
        bg_code = ""

    if mode in ("animation", "animation_2way"):
        elapsed = time.time() - animation_start_time
        logo_lines = LOGO_EXPERIMENTAL
        logo_height = len(logo_lines)
        logo_width = max(len(l) for l in logo_lines)
        
        # Base animation durations
        logo_reveal_duration = logo_width * 0.02
        subtitle_reveal_duration = 39 * 0.04
        
        # Timing keypoints
        t_logo_start = 5.0
        t_logo_end = t_logo_start + logo_reveal_duration
        t_sub_start = t_logo_end + 0.2
        t_sub_end = t_sub_start + subtitle_reveal_duration
        
        # Consistent layout height centering across all animation phases
        content_height = logo_height + 1 + 1 + 3 + 1
        start_y = max(0, (lines - content_height) // 2)
        
        # Menu configuration
        d_part = f"\033[1;38;2;0;219;99m[D] Default\033[22;39m" if mode == "default" else f"\033[38;2;120;120;120m[D] Default"
        e_part = f"\033[1;38;2;0;219;99m[E] Experimental\033[22;39m" if mode == "experimental" else f"\033[38;2;120;120;120m[E] Experimental"
        l_part = f"\033[1;38;2;0;219;99m[L] Legacy\033[22;39m" if mode == "legacy" else f"\033[38;2;120;120;120m[L] Legacy"
        a_part = f"\033[1;38;2;0;219;99m[A] Animate\033[22;39m" if mode == "animation" else f"\033[38;2;120;120;120m[A] Animate"
        w_part = f"\033[1;38;2;0;219;99m[W] 2-Way\033[22;39m" if mode == "animation_2way" else f"\033[38;2;120;120;120m[W] 2-Way"
        x_part = f"\033[1;38;2;0;219;99m[X] Border\033[22;39m" if show_border else f"\033[38;2;120;120;120m[X] Border"
        
        if bg_mode == "black":
            bg_label = "Pitch Black"
        elif bg_mode == "github_dark":
            bg_label = "GitHub Dark"
        else:
            bg_label = "Default"
            
        bg_part = f"\033[1;38;2;0;180;220m[B] BG: {bg_label}\033[22;39m"
        q_part = f"\033[38;2;220;60;60m[Q] Quit"
        
        menu_spacer = "  "
        menu_raw = f"[D] Default{menu_spacer}[E] Experimental{menu_spacer}[L] Legacy{menu_spacer}[A] Animate{menu_spacer}[W] 2-Way{menu_spacer}[X] Border{menu_spacer}[B] BG: {bg_label}{menu_spacer}[Q] Quit"
        menu_colored = f"{d_part}{FG_GRAY}{menu_spacer}{e_part}{FG_GRAY}{menu_spacer}{l_part}{FG_GRAY}{menu_spacer}{a_part}{FG_GRAY}{menu_spacer}{w_part}{FG_GRAY}{menu_spacer}{x_part}{FG_GRAY}{menu_spacer}{bg_part}{FG_GRAY}{menu_spacer}{q_part}"
 
        if elapsed < t_logo_start:
            # Phase 1: Countdown Screen (completely blank)
            buffer = ["\033[H"]
            for _ in range(lines - 1):
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
            buffer.append(build_centered_line("", "", cols, bg_code))
            
            sys.stdout.write("".join(buffer))
            sys.stdout.flush()
            return
 
        elif elapsed < t_logo_end:
            # Phase 2: Logo Reveal
            cols_to_show = max(0, int((elapsed - t_logo_start) / 0.02))
            
            buffer = ["\033[H"]
            for _ in range(start_y):
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                
            for i, line in enumerate(logo_lines):
                visible_chars = line[:cols_to_show]
                hidden_spaces = " " * (len(line) - len(visible_chars))
                color = LOGO_COLORS[i % len(LOGO_COLORS)]
                
                if 0 < len(visible_chars) < len(line):
                    # Add a white glowing lead character to act as the laser writer
                    logo_colored = f"{color}{visible_chars[:-1]}\033[1;37m{visible_chars[-1]}\033[22;39m{hidden_spaces}"
                else:
                    logo_colored = f"{color}{visible_chars}\033[39m{hidden_spaces}"
                    
                buffer.append(build_centered_line(line, logo_colored, cols, bg_code) + "\n")
                
            # Spacing & Empty Subtitle placeholder
            buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
            buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
            
            # Pad remaining lines
            current_lines = start_y + logo_height + 2
            for _ in range(lines - current_lines - 1):
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
            buffer.append(build_centered_line("", "", cols, bg_code))
            
            sys.stdout.write("".join(buffer))
            sys.stdout.flush()
            return
 
        elif elapsed < t_sub_end:
            # Phase 3: Subtitle Reveal
            chars_to_show = max(0, int((elapsed - t_sub_start) / 0.04))
            
            subtitle_raw = "🌿 Green by design. Powerful by nature."
            visible_sub = subtitle_raw[:chars_to_show]
            hidden_spaces = " " * (len(subtitle_raw) - len(visible_sub))
            
            if 0 < len(visible_sub) < len(subtitle_raw):
                sub_grad = colorize_horizontal_gradient(visible_sub[:-1])
                lead_char = visible_sub[-1]
                subtitle_colored = f"{sub_grad}\033[1;37m{lead_char}\033[22;39m{hidden_spaces}"
            else:
                subtitle_colored = colorize_horizontal_gradient(visible_sub) + hidden_spaces
            
            buffer = ["\033[H"]
            for _ in range(start_y):
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                
            # Render full logo
            for i, line in enumerate(logo_lines):
                color = LOGO_COLORS[i % len(LOGO_COLORS)]
                logo_colored = f"{color}{line}\033[39m"
                buffer.append(build_centered_line(line, logo_colored, cols, bg_code) + "\n")
                
            buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
            buffer.append(build_centered_line(subtitle_raw, subtitle_colored, cols, bg_code) + "\n")
            
            # Pad remaining lines
            current_lines = start_y + logo_height + 2
            for _ in range(lines - current_lines - 1):
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
            buffer.append(build_centered_line("", "", cols, bg_code))
            
            sys.stdout.write("".join(buffer))
            sys.stdout.flush()
            return
 
        if mode == "animation":
            t_menu_appear = t_sub_end + 5.0
            if elapsed < t_menu_appear:
                # Phase 3.5: Post-animation delay (5.0s) - Show full logo and subtitle, hide menu
                subtitle_raw = "🌿 Green by design. Powerful by nature."
                subtitle_colored = colorize_horizontal_gradient(subtitle_raw)
                
                buffer = ["\033[H"]
                for _ in range(start_y):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                    
                # Render full logo
                for i, line in enumerate(logo_lines):
                    color = LOGO_COLORS[i % len(LOGO_COLORS)]
                    logo_colored = f"{color}{line}\033[39m"
                    buffer.append(build_centered_line(line, logo_colored, cols, bg_code) + "\n")
                    
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line(subtitle_raw, subtitle_colored, cols, bg_code) + "\n")
                
                # Pad remaining lines (no menu)
                current_lines = start_y + logo_height + 2
                for _ in range(lines - current_lines - 1):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code))
                
                sys.stdout.write("".join(buffer))
                sys.stdout.flush()
                return
        else:  # mode == "animation_2way"
            t_rev_sub_start = t_sub_end + 2.0
            t_rev_sub_end = t_rev_sub_start + subtitle_reveal_duration
            t_rev_logo_start = t_rev_sub_end + 0.2
            t_rev_logo_end = t_rev_logo_start + logo_reveal_duration
            t_menu_appear = t_rev_logo_end + 5.0
 
            if elapsed < t_rev_sub_start:
                # Pause for 2.0s showing full logo and subtitle, no menu
                subtitle_raw = "🌿 Green by design. Powerful by nature."
                subtitle_colored = colorize_horizontal_gradient(subtitle_raw)
                
                buffer = ["\033[H"]
                for _ in range(start_y):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                for i, line in enumerate(logo_lines):
                    color = LOGO_COLORS[i % len(LOGO_COLORS)]
                    logo_colored = f"{color}{line}\033[39m"
                    buffer.append(build_centered_line(line, logo_colored, cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line(subtitle_raw, subtitle_colored, cols, bg_code) + "\n")
                
                # Pad remaining lines
                current_lines = start_y + logo_height + 2
                for _ in range(lines - current_lines - 1):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code))
                sys.stdout.write("".join(buffer))
                sys.stdout.flush()
                return
                
            elif elapsed < t_rev_sub_end:
                # Subtitle Reveal (reverse)
                chars_to_show = max(0, min(39, 39 - int((elapsed - t_rev_sub_start) / 0.04)))
                subtitle_raw = "🌿 Green by design. Powerful by nature."
                visible_sub = subtitle_raw[:chars_to_show]
                hidden_spaces = " " * (len(subtitle_raw) - len(visible_sub))
                
                if 0 < len(visible_sub) < len(subtitle_raw):
                    sub_grad = colorize_horizontal_gradient(visible_sub[:-1])
                    lead_char = visible_sub[-1]
                    subtitle_colored = f"{sub_grad}\033[1;37m{lead_char}\033[22;39m{hidden_spaces}"
                else:
                    subtitle_colored = colorize_horizontal_gradient(visible_sub) + hidden_spaces
                
                buffer = ["\033[H"]
                for _ in range(start_y):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                for i, line in enumerate(logo_lines):
                    color = LOGO_COLORS[i % len(LOGO_COLORS)]
                    logo_colored = f"{color}{line}\033[39m"
                    buffer.append(build_centered_line(line, logo_colored, cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line(subtitle_raw, subtitle_colored, cols, bg_code) + "\n")
                
                # Pad remaining lines
                current_lines = start_y + logo_height + 2
                for _ in range(lines - current_lines - 1):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code))
                sys.stdout.write("".join(buffer))
                sys.stdout.flush()
                return
                
            elif elapsed < t_rev_logo_start:
                # Subtitle completely blank, logo full (0.2s pause)
                buffer = ["\033[H"]
                for _ in range(start_y):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                for i, line in enumerate(logo_lines):
                    color = LOGO_COLORS[i % len(LOGO_COLORS)]
                    logo_colored = f"{color}{line}\033[39m"
                    buffer.append(build_centered_line(line, logo_colored, cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                
                # Pad remaining lines
                current_lines = start_y + logo_height + 2
                for _ in range(lines - current_lines - 1):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code))
                sys.stdout.write("".join(buffer))
                sys.stdout.flush()
                return
                
            elif elapsed < t_rev_logo_end:
                # Logo Reveal (reverse)
                cols_to_show = max(0, min(logo_width, logo_width - int((elapsed - t_rev_logo_start) / 0.02)))
                
                buffer = ["\033[H"]
                for _ in range(start_y):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                for i, line in enumerate(logo_lines):
                    visible_chars = line[:cols_to_show]
                    hidden_spaces = " " * (len(line) - len(visible_chars))
                    color = LOGO_COLORS[i % len(LOGO_COLORS)]
                    if 0 < len(visible_chars) < len(line):
                        logo_colored = f"{color}{visible_chars[:-1]}\033[1;37m{visible_chars[-1]}\033[22;39m{hidden_spaces}"
                    else:
                        logo_colored = f"{color}{visible_chars}\033[39m{hidden_spaces}"
                    buffer.append(build_centered_line(line, logo_colored, cols, bg_code) + "\n")
                    
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                
                # Pad remaining lines
                current_lines = start_y + logo_height + 2
                for _ in range(lines - current_lines - 1):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code))
                sys.stdout.write("".join(buffer))
                sys.stdout.flush()
                return
                
            elif elapsed < t_menu_appear:
                # Post-animation blank screen (5.0s menu delay)
                buffer = ["\033[H"]
                for _ in range(lines - 1):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code))
                sys.stdout.write("".join(buffer))
                sys.stdout.flush()
                return
                
            else:
                # Finished 2-way animation: Blank screen with menu at bottom
                buffer = ["\033[H"]
                for _ in range(start_y + logo_height + 3):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line(menu_raw, menu_colored, cols, bg_code) + "\n")
                
                current_lines = start_y + logo_height + 4
                for _ in range(lines - current_lines - 1):
                    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
                buffer.append(build_centered_line("", "", cols, bg_code))
                sys.stdout.write("".join(buffer))
                sys.stdout.flush()
                return

    # Phase 4 (Finished Animation) or standard static modes (default, legacy, experimental)
    if mode == "legacy":
        logo_lines = LOGO_LEGACY
    elif mode == "experimental" or mode == "animation" or mode == "animation_2way":
        logo_lines = LOGO_EXPERIMENTAL
    else:
        logo_lines = LOGO_DEFAULT

    logo_height = len(logo_lines)
    logo_width = max(len(l) for l in logo_lines)
    
    subtitle_raw = "🌿 Green by design. Powerful by nature."
    subtitle_colored = colorize_horizontal_gradient(subtitle_raw)
    
    # Menu configuration
    d_part = f"\033[1;38;2;0;219;99m[D] Default\033[22;39m" if mode == "default" else f"\033[38;2;120;120;120m[D] Default"
    e_part = f"\033[1;38;2;0;219;99m[E] Experimental\033[22;39m" if mode == "experimental" else f"\033[38;2;120;120;120m[E] Experimental"
    l_part = f"\033[1;38;2;0;219;99m[L] Legacy\033[22;39m" if mode == "legacy" else f"\033[38;2;120;120;120m[L] Legacy"
    a_part = f"\033[1;38;2;0;219;99m[A] Animate\033[22;39m" if mode == "animation" else f"\033[38;2;120;120;120m[A] Animate"
    w_part = f"\033[1;38;2;0;219;99m[W] 2-Way\033[22;39m" if mode == "animation_2way" else f"\033[38;2;120;120;120m[W] 2-Way"
    x_part = f"\033[1;38;2;0;219;99m[X] Border\033[22;39m" if show_border else f"\033[38;2;120;120;120m[X] Border"
    
    if bg_mode == "black":
        bg_label = "Pitch Black"
    elif bg_mode == "github_dark":
        bg_label = "GitHub Dark"
    else:
        bg_label = "Default"
        
    bg_part = f"\033[1;38;2;0;180;220m[B] BG: {bg_label}\033[22;39m"
    q_part = f"\033[38;2;220;60;60m[Q] Quit"
    
    menu_spacer = "  "
    menu_raw = f"[D] Default{menu_spacer}[E] Experimental{menu_spacer}[L] Legacy{menu_spacer}[A] Animate{menu_spacer}[W] 2-Way{menu_spacer}[X] Border{menu_spacer}[B] BG: {bg_label}{menu_spacer}[Q] Quit"
    menu_colored = f"{d_part}{FG_GRAY}{menu_spacer}{e_part}{FG_GRAY}{menu_spacer}{l_part}{FG_GRAY}{menu_spacer}{a_part}{FG_GRAY}{menu_spacer}{w_part}{FG_GRAY}{menu_spacer}{x_part}{FG_GRAY}{menu_spacer}{bg_part}{FG_GRAY}{menu_spacer}{q_part}"

    if show_border:
        box_w = 64
        box_h = 16
        
        # Calculate static vertical centering row for the logo
        static_content_height = logo_height + 1 + 1 + 3 + 1
        static_logo_y = max(0, (lines - static_content_height) // 2)
        
        # The box should start at static_logo_y - 4, so the logo (which starts on row 4 inside the box)
        # lands exactly on static_logo_y!
        start_y = max(0, static_logo_y - 4)
        
        # Calculate horizontal centering for the box itself
        pad_left = (cols - 1 - box_w) // 2
        pad_right = cols - 1 - box_w - pad_left
        
        # Create inner content list (exactly box_h - 2 lines, i.e., 14 lines)
        inner_lines = []
        # 3 empty lines on top
        for _ in range(3):
            inner_lines.append(("", ""))
        # Logo lines
        for i, line in enumerate(logo_lines):
            color = LOGO_COLORS[i % len(LOGO_COLORS)]
            logo_colored = f"{color}{line}\033[39m"
            inner_lines.append((line, logo_colored))
        # 1 spacer
        inner_lines.append(("", ""))
        # Subtitle
        inner_lines.append((subtitle_raw, subtitle_colored))
        # 3 empty lines on bottom
        for _ in range(3):
            inner_lines.append(("", ""))
            
        # Draw screen
        buffer = ["\033[H"]
        
        # Empty space before box
        for _ in range(start_y):
            buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
            
        # Top border line
        top_raw = "┌" + "─" * (box_w - 2) + "┐"
        top_colored = f"{BOX_COLOR}{top_raw}\033[39m"
        buffer.append(f"{bg_code}{' ' * pad_left}{top_colored}{bg_code}{' ' * pad_right}\n")
        
        # Inner lines with vertical borders
        for raw, colored in inner_lines:
            # Align inner text precisely with its static centered position
            pad_left_static = (cols - 1 - display_len(raw)) // 2
            inner_pad_left = max(0, pad_left_static - pad_left - 1)
            inner_pad_right = box_w - 2 - display_len(raw) - inner_pad_left
            
            line_colored_part = f"{BOX_COLOR}│\033[39m{' ' * inner_pad_left}{colored}{' ' * inner_pad_right}{BOX_COLOR}│\033[39m"
            buffer.append(f"{bg_code}{' ' * pad_left}{line_colored_part}{bg_code}{' ' * pad_right}\n")
            
        # Bottom border line
        bot_raw = "└" + "─" * (box_w - 2) + "┘"
        bot_colored = f"{BOX_COLOR}{bot_raw}\033[39m"
        buffer.append(f"{bg_code}{' ' * pad_left}{bot_colored}{bg_code}{' ' * pad_right}\n")
        
        # Pad remaining lines (including menu)
        current_lines = start_y + box_h
        remaining_empty = (lines - 2) - current_lines
        
        if remaining_empty > 0:
            for _ in range(remaining_empty):
                buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
        else:
            buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
            
        # Menu line
        buffer.append(build_centered_line(menu_raw, menu_colored, cols, bg_code) + "\n")
        buffer.append(build_centered_line("", "", cols, bg_code))
        
        sys.stdout.write("".join(buffer))
        sys.stdout.flush()
        return

    content_height = logo_height + 1 + 1 + 3 + 1
    start_y = max(0, (lines - content_height) // 2)
    
    buffer = ["\033[H"]
    
    for _ in range(start_y):
        buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
        
    for i, line in enumerate(logo_lines):
        color = LOGO_COLORS[i % len(LOGO_COLORS)]
        logo_colored = f"{color}{line}\033[39m"
        buffer.append(build_centered_line(line, logo_colored, cols, bg_code) + "\n")
        
    buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
    buffer.append(build_centered_line(subtitle_raw, subtitle_colored, cols, bg_code) + "\n")
    
    current_line_count = start_y + logo_height + 2
    remaining_empty = (lines - 2) - current_line_count
    
    if remaining_empty > 0:
        for _ in range(remaining_empty):
            buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
    else:
        buffer.append(build_centered_line("", "", cols, bg_code) + "\n")
        
    buffer.append(build_centered_line(menu_raw, menu_colored, cols, bg_code) + "\n")
    buffer.append(build_centered_line("", "", cols, bg_code))
    
    sys.stdout.write("".join(buffer))
    sys.stdout.flush()

def main():
    enable_ansi()
    
    # Hide cursor and start screen buffer
    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.flush()
    
    mode = "default"
    bg_mode = "black"
    show_border = False
    animation_start_time = 0.0
    last_size = (0, 0)
    
    # Platform-specific non-blocking keyboard input
    if os.name == 'nt':
        import msvcrt
        def get_key():
            if msvcrt.kbhit():
                try:
                    ch = msvcrt.getch()
                    if ch in (b'\x00', b'\xe0'):
                        msvcrt.getch()
                        return None
                    return ch.decode('utf-8', errors='ignore').lower()
                except Exception:
                    return None
            return None
    else:
        import select
        import tty
        import termios
        def get_key():
            if select.select([sys.stdin], [], [], 0)[0]:
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(sys.stdin.fileno())
                    ch = sys.stdin.read(1).lower()
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                return ch
            return None

    try:
        # Perform an initial screen clear to black background
        sys.stdout.write("\033[48;2;0;0;0m\033[2J")
        sys.stdout.flush()
        
        while True:
            cols, lines = get_terminal_size()
            current_size = (cols, lines)
            
            # Only clear screen with \033[2J when the terminal window size changes
            if current_size != last_size:
                if bg_mode == "black":
                    sys.stdout.write("\033[48;2;0;0;0m\033[2J")
                elif bg_mode == "github_dark":
                    sys.stdout.write("\033[48;2;13;17;23m\033[2J")
                else:
                    sys.stdout.write("\033[0m\033[2J")
                sys.stdout.flush()
                last_size = current_size
                
            draw_screen(mode, bg_mode, cols, lines, animation_start_time, show_border)
            
            key = get_key()
            if key in ('q', '\x03'):  # 'q' or Ctrl+C
                break
            elif key == 'd':
                mode = "default"
            elif key == 'e':
                mode = "experimental"
            elif key == 'l':
                mode = "legacy"
            elif key == 'b':
                if bg_mode == "black":
                    bg_mode = "github_dark"
                elif bg_mode == "github_dark":
                    bg_mode = "default"
                else:
                    bg_mode = "black"
            elif key == 'a':
                show_border = False
                mode = "animation"
                animation_start_time = time.time()
            elif key == 'w':
                show_border = False
                mode = "animation_2way"
                animation_start_time = time.time()
            elif key == 'x':
                show_border = not show_border
                
            time.sleep(0.02)
            
    except KeyboardInterrupt:
        pass
    finally:
        # Reset colors, clear screen, restore cursor
        sys.stdout.write(f"{RESET_ALL}\033[2J\033[H{SHOW_CURSOR}")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
