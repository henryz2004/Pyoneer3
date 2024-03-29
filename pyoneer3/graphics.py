import pygame
from collections import namedtuple
from typing import List, Union
pygame.init()


XYComplex = namedtuple('XYComplex', 'xScale xOffset yScale yOffset')
XYSimple = namedtuple('XYSimple', 'xOffset yOffset')


def to_simple(coord: XYComplex, surf: pygame.Surface) -> XYSimple:

    return XYSimple(coord[1] + surf.get_width() * coord[0],
                    coord[3] + surf.get_height() * coord[2])


def extract_offsets(coord: XYComplex) -> XYSimple:

    return XYSimple(coord[1], coord[3])


def clamp_color(rgb):

    r = rgb[0]
    g = rgb[1]
    b = rgb[2]

    if r < 0:
        r = 0
    elif r > 255:
        r = 255

    if g < 0:
        g = 0
    elif g > 255:
        g = 255

    if b < 0:
        b = 0
    elif b > 255:
        b = 255

    return r, g, b


def ppm_collide(this, other) -> tuple:
    """Checks for pixel-perfect collision with another object that has a rect and a mask. Returns collision point or None"""
    # TODO: Optimization absolute position does not need to be frequently calculated because position information is stored in self.rect

    other_rel_x = other.rect.topleft[0] - this.rect.topleft[0]
    other_rel_y = other.rect.topleft[1] - this.rect.topleft[1]

    overlap = this.mask.overlap(other.mask, (other_rel_x, other_rel_y))

    return (overlap[0] + this.rect.topleft[0], overlap[1] + this.rect.topleft[1]) if overlap else None


def ppm_detected(this, other) -> bool:
    """Identical as ppm_collide() but returns a boolean"""

    collision = ppm_collide(this, other)
    return bool(collision)


class Screen:

    def __init__(self, screen):

        self.screen = screen
        self.scenes: List[Scene] = []

    def render(self, background_color):

        self.screen.fill(background_color)

        self.scenes.sort(key=lambda s: s.priority)
        for scene in self.scenes:
            if scene and scene.active:
                scene.draw()


class Scene:

    def __init__(self, screen, active=False, render_priority=1):

        self.active = active
        self.surf = screen.screen
        self.priority = render_priority
        self.children = []

        screen.scenes.append(self)

    def get_descendants(self):

        descendants = self.children[:]
        for child in self.children:
            descendants.extend(child.get_descendants())
        return descendants

    def draw(self):

        self.children.sort(key=lambda c: c.priority)
        for child in self.children:
            child.draw_seq()


class UIElement:
    # TODO: XYComplex position

    def __init__(self, pos: XYComplex, surf, fill_color=None, render_priority=1):
        super().__init__()

        self.name = ""
        self.rel_pos = pos               # Tuple in Roblox UDim2 format (xScale, xOffset, yScale, yOffset)

        self.surf = surf
        self.c_surf = None               # MANDATORY update call before drawing!
        self.rect = None
        self.fill_color = fill_color if fill_color else (0, 0, 0)       # *NO FUNCTIONALITY, SIMPLY A MARKER*
        self.priority = render_priority  # Prioritizes which elements get rendered first. Higher numbers take precedence
        self.visible = True

        # Dictionary of all handler functions (functions that take in/handle events)
        self.active = True          # Determines whether events will be handled
        self.handlers = {'mbd': None, 'mover': None,  'menter': None, 'mexit': None, 'uevent': []}
        self.mouse_inside = False       # Event flag used for mouse-enter and mouse-exit events

        self.parent: Union[Scene, UIElement]  = None
        self.children = []

    def set_parent(self, parent):

        self.parent = parent
        self.parent.children.append(self)

    def unparent(self):

        self.parent.children.remove(self)
        self.parent = None

    def get_descendants(self):

        descendants = self.children[:]
        for child in self.children:
            descendants.extend(child.get_descendants())
        return descendants

    def get_child_of_name(self, name):

        for name in self.children:
            if child.name == name:
                return child

        return None

    def offset(self, offset: XYComplex):

        self.rel_pos = tuple(self.rel_pos[i] + c for i, c in enumerate(offset))

    def center_position(self, pos: XYComplex):

        assert self.surf, "Cannot center without surface"

        self.rel_pos = (
            pos[0],
            pos[1] - self.surf.get_width()/2,
            pos[2],
            pos[3] - self.surf.get_height()/2
        )

    def calculate_absolute_position(self):

        # Calculate absolute position of parents in their parents up to top
        position_chain: List[XYSimple] = []
        current_object = self
        while isinstance(current_object, UIElement):
            position_chain.append(to_simple(current_object.rel_pos, current_object.parent.surf))

            current_object = current_object.parent

        # Sum up position_chain to get absolute position of self by unzipping to get list of x and y values and then sum
        individual_xy = list(zip(*position_chain))
        return XYSimple(int(sum(individual_xy[0])), int(sum(individual_xy[1])))

    def update_rect(self):

        self.rect = self.surf.get_rect()
        self.rect.topleft = self.calculate_absolute_position()

    def update(self):

        assert self.surf, "Attempted to update without surface"

        self.c_surf = self.surf.copy()
        self.update_rect()

    def draw_children(self, reset_surf=True):

        assert self.surf, "Attempted to render UIElement children without surface"

        # Only draw children if self is visible
        if not self.visible:
            return

        if reset_surf:
            # Reset self.surf by overriding it with c_surf
            self.surf = self.c_surf.copy()

        self.children.sort(key=lambda c: c.priority)       # Sort children in order based off of priority
        for child in self.children:
            child.draw_seq()

    def draw(self):

        assert self.surf, "Attempted to render UIElement without surface"
        assert self.parent, "Attempted to draw on nothing"

        # Only draw self if self is visible
        if not self.visible:
            return

        self.parent.surf.blit(self.surf, to_simple(self.rel_pos, self.parent.surf))

    def draw_seq(self):

        self.draw_children()
        self.draw()

    # Event methods
    def bind_mbd(self, handler):
        """Bind handler to mouse button down event takes in self and event"""

        self.handlers['mbd'] = handler

    def bind_mover(self, handler):
        """Bind handler to mouse over event takes in self and event"""

        self.handlers['mover'] = handler

    def bind_menter(self, handler):

        self.handlers['menter'] = handler

    def bind_mexit(self, handler):

        self.handlers['mexit'] = handler

    def bind_u(self, handler):
        """Universal event handler function takes in self and event"""

        self.handlers['uevent'].append(handler)

    def unbind_mbd(self):

        self.handlers['mbd'] = None

    def unbind_mover(self):

        self.handlers['mover'] = None

    def unbind_menter(self):

        self.handlers['menter'] = None

    def unbind_mexit(self):

        self.handlers['mexit'] = None

    def unbind_u(self, index=-1):

        return self.handlers['uevent'].pop(index)

    def handle_event(self, event, tick=None):

        if not self.active:
            return

        mouse_motion = False

        # Call mouse-button down handler
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.rect.collidepoint(event.pos):
                    if self.handlers['mbd']:
                        self.handlers['mbd'](self, event)

        elif event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(event.pos):
                mouse_motion = True     # Flag used for mexit event

                # Update mouse_inside flag for menter and mexit events and handle menter event
                # If mouse was not inside on the previous event (but now is), mouse has entered
                if not self.mouse_inside:
                    self.mouse_inside = True
                    if self.handlers['menter']:
                        self.handlers['menter'](self, event)

                # Handle mover event
                if self.handlers['mover']:
                    self.handlers['mover'](self, event)

            # If the mouse didn't move inside self.rect and it used to be inside, mouse has exited
            if not mouse_motion and self.mouse_inside:
                self.mouse_inside = False
                if self.handlers['mexit']:
                    self.handlers['mexit'](self, event)

        for uhandler in self.handlers['uevent']:
            uhandler(self, event, tick)  # Handles all non-default events, pass in tick (time elasped)


class ScrollingFrame(UIElement):
    """Simple Vertical Scroller"""

    def __init__(self, pos: XYComplex, scroll_limits: XYSimple, window_size: XYComplex, scroll_fill=None, render_priority=1):
        super().__init__(pos, None, render_priority)

        self.window = None
        self.window_size: XYComplex = window_size

        self.scroll_limits: XYSimple = scroll_limits
        self.scroll_pos = 0
        self.scroll_speed = 10
        self.scrollable = True
        self.mouse_over = False     # Whether the mouse is over the scrolling frame

        self.scroll_fill = scroll_fill if scroll_fill else (230, 230, 230)
        self.scrollbar_surf = None
        self.scrollbar_padding = 4
        self.scrollbar_width = 2
        self.show_scrollbar = True

        self.bind_u(self.scroll_handler)
        self.bind_menter(self._menter)
        self.bind_mexit(self._mexit)

    def _menter(self, *_):
        self.mouse_over = True

    def _mexit(self, *_):
        self.mouse_over = False

    def update_rect(self):
        """Overrides update_rect of parent - rect is not self.surf's rect, it is self.window's rect"""

        self.rect = self.window.get_rect()
        self.rect.topleft = self.calculate_absolute_position()

    def update(self):

        window_size_simple: XYSimple = to_simple(self.window_size, self.parent.surf)

        # Move contents of scrolling frame
        self.window = pygame.Surface(window_size_simple, pygame.SRCALPHA)
        self.window.fill((0, 0, 0, 0))
        self.surf = pygame.Surface(self.scroll_limits, pygame.SRCALPHA)
        self.surf.fill((0, 0, 0, 0))
        self.scroll()       # Blits self.surf onto self.window at correct position

        # Create (vertical) scrollbar
        window_percent = window_size_simple[1] / self.scroll_limits[1]          # Percent of total area being shown on window
        scrollbar_freedom = (window_size_simple[1] - self.scrollbar_padding*2)  # How tall the entire scrolling part is

        self.scrollbar_surf = pygame.Surface(
            (self.scrollbar_width, window_percent * scrollbar_freedom),
            pygame.SRCALPHA
        )
        self.scrollbar_surf.fill(self.scroll_fill)

        super().update()

    def draw(self):

        assert self.window, "Attempted to render UIElement without window surface"
        assert self.parent, "Attempted to draw on nothing"

        # Only draw self if self is visible
        if not self.visible:
            return

        window_size_simple: XYSimple = to_simple(self.window_size, self.parent.surf)
        scrollbar_progress = -self.scroll_pos / self.scroll_limits[1]  # Percent scrollbar should be down the screen
        scrollbar_freedom = (window_size_simple[1] - self.scrollbar_padding*2)

        self.scroll()

        # Blit scrollbar
        if self.show_scrollbar and self.scrollbar_surf.get_height() < scrollbar_freedom:
            self.window.blit(
                self.scrollbar_surf,
                to_simple(
                    (1, -int(self.scrollbar_padding) - self.scrollbar_width,
                     0, int(self.scrollbar_padding) + scrollbar_progress * scrollbar_freedom),
                    self.window
                )
            )
        self.parent.surf.blit(self.window, to_simple(self.rel_pos, self.parent.surf))

    def scroll_handler(self, uie, event, tick):

        if not self.mouse_over or not self.scrollable or not self.parent.surf:
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:           # Scroll up
                absolute_window_size = to_simple(self.window_size, self.parent.surf)
                self.scroll_pos += min(
                    self.scroll_speed, -self.scroll_pos
                )

            elif event.button == 5:         # Scroll down
                absolute_window_size = to_simple(self.window_size, self.parent.surf)

                if absolute_window_size[1] < self.scroll_limits[1]:
                    self.scroll_pos -= min(
                        self.scroll_speed, self.scroll_limits[1] + self.scroll_pos - absolute_window_size[1]
                    )

            self.scroll()

    def scroll(self):

        self.window.fill((0, 0, 0, 0))
        self.window.blit(self.surf, (0, self.scroll_pos))


class Option(UIElement):

    def __init__(self, pos: XYComplex, surf, fill_color=None, render_priority=1):
        super().__init__(pos, surf, fill_color, render_priority)

        self.selected = False


class Text(UIElement):

    def __init__(self, pos: XYComplex, size: XYSimple, text, fill_color, font, *font_args, anchor=1, render_priority=1, wrap_multiline=True):
        # noinspection
        super().__init__(pos, None, fill_color, render_priority)

        self.anchor = anchor        # Position of text - top left, center

        self._text = text
        self.font = font
        self.font_args = list(font_args)
        self.text_surf = None
        self.surf = pygame.Surface(size, pygame.SRCALPHA)
        self.wrap = wrap_multiline

        self.draw_text()

    def render_text(self):

        # TODO: FIX
        if self.wrap:

            # Handle multilines
            lines = [line.split() for line in str(self._text).splitlines()]
            space = self.font.size(' ')[0]      # Width of a space
            max_width, max_height = self.surf.get_size()
            render_list = []        # List of lines (lists of word surfaces and their positions to be rendered on self.text_surf) and their x offset

            pos = (0, 0) if self.anchor == 0 else (int(max_width/2), int(max_height/2))
            x, y = pos
            n_lines = 0

            for i, line in enumerate(lines):
                line_surfs = [[], 0]        # List of word surfaces on this line and the x offset of the line (for centering)
                for j, word in enumerate(line):

                    # Render, check bounds
                    word_surf = self.font.render(word, *self.font_args)
                    word_w, word_h = word_surf.get_size()

                    # If row is too long start new row
                    if x + 0.5*word_w + line_surfs[1] >= max_width:
                        render_list.append(line_surfs)
                        line_surfs = [[], 0]

                        x = pos[0]
                        y += word_h

                        if self.anchor == 1:
                            n_lines += 1

                    line_surfs[0].append((word_surf, (x, y)))
                    if self.anchor == 1:
                        line_surfs[1] -= 0.5*(word_w+(space if j < len(line)-1 else 0))
                    x += word_w + space

                render_list.append(line_surfs)
                x = pos[0]
                y += word_h

                if self.anchor == 1:
                    n_lines += 1# if i > 0 else 0

            self.text_surf = pygame.Surface((max_width, max_height), pygame.SRCALPHA)
            self.text_surf.fill((0, 0, 0, 0))
            for line in render_list:
                for word_surf, draw_pos in line[0]:
                    if self.anchor == 1:
                        self.text_surf.blit(word_surf, (draw_pos[0] + line[1], draw_pos[1] - n_lines * word_h/2))
                    else:
                        self.text_surf.blit(word_surf, (draw_pos[0], draw_pos[1]))

        else:
            self.text_surf = self.font.render(str(self._text), *self.font_args)

    def blit_text(self):

        # DO NOT UPDATE_SURFACE, THAT IS UP TO USER
        self.surf.fill(self.fill_color)

        # Position text based off of sel.anchor = 1 = center, 0 = topleft
        if self.anchor == 1:
            self.surf.blit(
                self.text_surf,
                (int(self.surf.get_width() / 2) - int(self.text_surf.get_width() / 2),
                 int(self.surf.get_height() / 2) - int(self.text_surf.get_height() / 2))
            )     # Blit text to center of button

        else:
            self.surf.blit(self.text_surf, (0, 0))

    def draw_text(self):
        """Renders and blits text surf on final surf"""

        self.render_text()
        self.blit_text()

    @property
    def text(self):

        return self._text

    @text.setter
    def text(self, value):

        self._text = str(value)
        self.draw_text()


class Image(UIElement):

    def __init__(self, pos: XYComplex, image_path, render_priority=1):
        if isinstance(image_path, str):
            super().__init__(pos, pygame.image.load(image_path).convert_alpha(), render_priority)
        else:
            super().__init__(pos, image_path, render_priority)

        self.image_path = image_path


class Sprite(Image, pygame.sprite.Sprite):

    def __init__(self, pos: XYComplex, image_path, anchor=1, render_priority=1, mask=True):
        super().__init__(pos, image_path, render_priority)

        self.anchor = anchor
        self.rot = 0  # Sprite rotation

        self.has_mask = mask
        if self.has_mask:
            self.mask = None

    def update_rect(self):

        rotated_surf = pygame.transform.rotate(self.surf, self.rot)

        self.rect = rotated_surf.get_rect()

        # Anchor at topleft
        if self.anchor == 0:
            self.rect.topleft = self.calculate_absolute_position()

        # Anchor at mid:
        elif self.anchor == 1:
            self.rect.center = self.calculate_absolute_position()

    def update(self):

        super().update()

        if self.has_mask:
            self.mask = pygame.mask.from_surface(self.surf)     # Update sprite mask

    def draw(self, bb=False):
        """bb = Bounding box, flag to determine whether or not the bounding box of the sprite will be drawn """

        assert self.surf, "Attempted to render UIElement without surface"
        assert self.parent, "Attempted to draw on nothing"

        # Only draw self if self is visible
        if not self.visible:
            return

        rotated_surf = pygame.transform.rotate(self.surf, self.rot)

        if bb:
            pygame.draw.rect(rotated_surf, (255, 255, 255), (0, 0, rotated_surf.get_width(), rotated_surf.get_height()), 1)

        if self.anchor == 0:
            self.parent.surf.blit(rotated_surf, to_simple(self.rel_pos, self.parent.surf))

        else:
            x, y = to_simple(self.rel_pos, self.parent.surf)
            self.parent.surf.blit(rotated_surf, (x - rotated_surf.get_width()/2, y - rotated_surf.get_height()/2))