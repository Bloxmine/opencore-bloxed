// layerdump3.m: diagnostic only. dump_layers3() returns the CALayer tree of the app's visible windows, with blend
// modes, filters, opacity and background alpha. No constructor: does nothing until called from the debugger.
#import <AppKit/AppKit.h>
#import <QuartzCore/QuartzCore.h>
static void walk(CALayer *l, int depth, NSMutableString *out) {
    CGRect f = l.frame; id c = l.contents;
    NSString *bg = @"-";
    if (l.backgroundColor) { const CGFloat *k = CGColorGetComponents(l.backgroundColor); size_t n = CGColorGetNumberOfComponents(l.backgroundColor);
        bg = [NSString stringWithFormat:@"a=%.2f(%zu comps, c0=%.2f)", CGColorGetAlpha(l.backgroundColor), n, n ? k[0] : 0]; }
    NSString *cf = l.compositingFilter ? [NSString stringWithFormat:@"%@", l.compositingFilter] : @"-";
    NSString *filters = l.filters.count ? [[l.filters valueForKey:@"description"] componentsJoinedByString:@","] : @"-";
    NSString *bf = l.backgroundFilters.count ? [[l.backgroundFilters valueForKey:@"description"] componentsJoinedByString:@","] : @"-";
    [out appendFormat:@"%*s%@ '%@' (%.0f,%.0f %.0fx%.0f) op=%.2f hidden=%d opaque=%d bg=%@ compFilter=%@ filters=%@ bgFilters=%@ contents=%@ delegate=%@\n",
        depth * 2, "", NSStringFromClass([l class]), l.name ?: @"", f.origin.x, f.origin.y, f.size.width, f.size.height, l.opacity, l.hidden, l.opaque, bg, cf, filters, bf,
        c ? NSStringFromClass([c class]) : @"nil", l.delegate ? NSStringFromClass([(id)l.delegate class]) : @"-"];
    for (CALayer *s in l.sublayers) walk(s, depth + 1, out);
}
__attribute__((visibility("default"))) const char *dump_layers3(void) {
    __block NSMutableString *out = [NSMutableString string];
    void (^work)(void) = ^{
        for (NSWindow *w in NSApp.windows) {
            if (!w.isVisible || !w.contentView.layer) continue;
            [out appendFormat:@"== window '%@' %@\n", w.title, NSStringFromClass([w class])];
            CALayer *root = w.contentView.layer; while (root.superlayer) root = root.superlayer;
            walk(root, 0, out);
        }
    };
    if ([NSThread isMainThread]) work(); else dispatch_sync(dispatch_get_main_queue(), work);
    static NSString *keep; keep = [out copy];
    return keep.UTF8String;
}
