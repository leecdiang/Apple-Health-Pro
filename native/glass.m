// Public AppKit only. Preserve Qt's NSView hierarchy and coordinate ownership.
#import <Cocoa/Cocoa.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>

typedef void (*HPPathCallback)(const char *path);

// Qt palettes do not set NSWindow appearance. Glass/titlebar compositing must
// receive the same override; mode 0 removes it so macOS can follow the system.
void hp_window_appearance(void *pointer, int mode) {
    if (![NSThread isMainThread] || !pointer) return;
    NSView *view = (__bridge NSView *)pointer;
    NSAppearance *appearance = mode == 0 ? nil : [NSAppearance appearanceNamed:
        mode == 2 ? NSAppearanceNameDarkAqua : NSAppearanceNameAqua];
    view.window.appearance = appearance;
    view.window.contentView.appearance = appearance;
    view.appearance = appearance;
}

int hp_window_appearance_matches(void *pointer, int mode) {
    if (![NSThread isMainThread] || !pointer) return 0;
    NSView *view = (__bridge NSView *)pointer;
    if (!view.window) return 0;
    if (mode == 0) return view.window.appearance == nil && view.appearance == nil;
    NSString *expected = mode == 2 ? NSAppearanceNameDarkAqua : NSAppearanceNameAqua;
    return [[view.window.effectiveAppearance bestMatchFromAppearancesWithNames:
        @[NSAppearanceNameAqua, NSAppearanceNameDarkAqua]] isEqualToString:expected];
}

// Use AppKit's own sheet and UTType filter rather than Qt's filename-filter adapter.
void hp_choose_path(void *pointer, const char *directory, int folders, int dark,
                    HPPathCallback completion) {
    if (![NSThread isMainThread] || !pointer || !completion) return;
    NSView *view = (__bridge NSView *)pointer;
    NSOpenPanel *panel = [NSOpenPanel openPanel];
    panel.title = folders ? @"选择输出文件夹" : @"选择 Apple 健康数据";
    panel.prompt = folders ? @"选择" : @"打开";
    panel.canChooseFiles = !folders;
    panel.canChooseDirectories = folders;
    panel.canCreateDirectories = folders;
    panel.allowsMultipleSelection = NO;
    panel.appearance = [NSAppearance appearanceNamed:dark ? NSAppearanceNameDarkAqua : NSAppearanceNameAqua];
    if (directory && directory[0])
        panel.directoryURL = [NSURL fileURLWithPath:[NSString stringWithUTF8String:directory] isDirectory:YES];
    if (!folders) {
        if (@available(macOS 11.0, *)) panel.allowedContentTypes = @[UTTypeZIP];
        else panel.allowedFileTypes = @[@"zip"];
    }
    [panel beginSheetModalForWindow:view.window completionHandler:^(NSModalResponse result) {
        completion(result == NSModalResponseOK ? panel.URL.path.UTF8String : NULL);
    }];
}

@interface HPGlassHost : NSObject
@property(strong) NSView *effect;
@property(weak) NSView *content;
@property(weak) NSView *parent;
@property BOOL liquid;
@end
@implementation HPGlassHost
@end

int hp_accessibility(void) {
    NSWorkspace *w = NSWorkspace.sharedWorkspace;
    return (w.accessibilityDisplayShouldReduceTransparency ? 1 : 0)
         | (w.accessibilityDisplayShouldReduceMotion ? 2 : 0)
         | (w.accessibilityDisplayShouldIncreaseContrast ? 4 : 0);
}

// Glass is a backdrop sibling below the transparent Qt native surface.
// Reparenting a QNSView breaks Qt backing-store coordinates and duplicates controls.
void *hp_glass_attach(void *pointer) {
    if (![NSThread isMainThread] || !pointer) return NULL;
    NSView *view = (__bridge NSView *)pointer;
    if (!view.superview || !view.window) return NULL;
    HPGlassHost *host = [HPGlassHost new];
    host.parent = view.superview;
    host.content = view;
    NSRect frame = view.frame;
    if (@available(macOS 26.0, *)) {
        NSGlassEffectView *glass = [[NSGlassEffectView alloc] initWithFrame:frame];
        glass.style = NSGlassEffectViewStyleRegular;
        glass.cornerRadius = 22;
        glass.contentView = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, frame.size.width, frame.size.height)];
        host.effect = glass;
        host.liquid = YES;
    } else {
        NSVisualEffectView *glass = [[NSVisualEffectView alloc] initWithFrame:frame];
        glass.material = NSVisualEffectMaterialHeaderView;
        glass.blendingMode = NSVisualEffectBlendingModeWithinWindow;
        glass.state = NSVisualEffectStateFollowsWindowActiveState;
        glass.wantsLayer = YES;
        glass.layer.cornerRadius = 22;
        glass.layer.masksToBounds = YES;

        host.effect = glass;
    }
    [host.parent addSubview:host.effect positioned:NSWindowBelow relativeTo:view];
    return (__bridge_retained void *)host;
}

void hp_glass_sync(void *pointer, int dark) {
    if (!pointer || ![NSThread isMainThread]) return;
    HPGlassHost *host = (__bridge HPGlassHost *)pointer;
    NSView *parent = host.parent;
    if (!parent) return;
    host.effect.frame = host.content.frame;
    host.effect.hidden = host.content.hidden;
    host.effect.appearance = [NSAppearance appearanceNamed:dark ? NSAppearanceNameDarkAqua : NSAppearanceNameAqua];
    if (@available(macOS 26.0, *)) {
        if (host.liquid) {
            // Qt text cannot follow AppKit's automatic foreground adaptation.
            // A neutral dark tint keeps light text readable over bright backdrops.
            ((NSGlassEffectView *)host.effect).tintColor = dark
                ? [NSColor colorWithSRGBRed:0.10 green:0.12 blue:0.16 alpha:0.35] : nil;
        }
    }
    host.effect.needsDisplay = YES;
}

int hp_glass_kind(void *pointer) {
    return pointer && ((__bridge HPGlassHost *)pointer).liquid ? 2 : 1;
}

// Used by the native smoke check: Qt must retain its parent and exact geometry.
int hp_glass_valid(void *pointer) {
    if (!pointer || ![NSThread isMainThread]) return 0;
    HPGlassHost *host = (__bridge HPGlassHost *)pointer;
    return host.content.superview == host.parent
        && host.effect.superview == host.parent
        && NSEqualRects(host.content.frame, host.effect.frame)
        && host.effect.frame.size.width > 0 && host.effect.frame.size.height > 0;
}

int hp_glass_appearance_matches(void *pointer, int dark) {
    if (!pointer || ![NSThread isMainThread]) return 0;
    HPGlassHost *host = (__bridge HPGlassHost *)pointer;
    NSString *expected = dark ? NSAppearanceNameDarkAqua : NSAppearanceNameAqua;
    BOOL match = [[host.effect.effectiveAppearance bestMatchFromAppearancesWithNames:
        @[NSAppearanceNameAqua, NSAppearanceNameDarkAqua]] isEqualToString:expected];
    if (@available(macOS 26.0, *)) {
        if (host.liquid) match = match && (((NSGlassEffectView *)host.effect).tintColor != nil) == !!dark;
    }
    return match;
}

void hp_glass_detach(void *pointer) {
    if (!pointer || ![NSThread isMainThread]) return;
    HPGlassHost *host = (__bridge_transfer HPGlassHost *)pointer;
    [host.effect removeFromSuperview];
}
