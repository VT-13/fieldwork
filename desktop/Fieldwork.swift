import Cocoa
import WebKit
class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
 var window: NSWindow!
 var web: WKWebView!
 func applicationDidFinishLaunching(_ notification: Notification) {
  let menu = NSMenu(); let item = NSMenuItem(); let sub = NSMenu()
  sub.addItem(withTitle: "Quit Fieldwork", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
  item.submenu = sub; menu.addItem(item); NSApp.mainMenu = menu
  window = NSWindow(contentRect: NSRect(x:0,y:0,width:1200,height:820),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
  window.title = "Fieldwork — Vihaan’s Internship Workspace"
  web = WKWebView(); web.navigationDelegate = self; web.uiDelegate = self
  window.contentView = web; window.center(); window.makeKeyAndOrderFront(nil)
  NSApp.activate(ignoringOtherApps:true)
  load()
 }
 func load() { web.load(URLRequest(url:URL(string:"http://localhost:3000")!)) }
 func webView(_ webView:WKWebView,didFailProvisionalNavigation navigation:WKNavigation!,withError error:Error) {
  web.loadHTMLString("<html><body style='font:20px system-ui;padding:60px'><h1>Starting your workspace…</h1><p>The background service is reconnecting. This window will retry automatically.</p></body></html>",baseURL:nil)
  DispatchQueue.main.asyncAfter(deadline:.now()+5){ self.load() }
 }
 func webView(_ webView:WKWebView,decidePolicyFor action:WKNavigationAction,decisionHandler:@escaping(WKNavigationActionPolicy)->Void) {
  if let url=action.request.url, let host=url.host, host != "localhost" && host != "127.0.0.1" { NSWorkspace.shared.open(url); decisionHandler(.cancel); return }
  decisionHandler(.allow)
 }
 func webView(_ webView:WKWebView,createWebViewWith configuration:WKWebViewConfiguration,for action:WKNavigationAction,windowFeatures:WKWindowFeatures)->WKWebView? {
  if let url=action.request.url { NSWorkspace.shared.open(url) }; return nil
 }
 func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool { return true }
}
let app=NSApplication.shared
let delegate=AppDelegate()
app.delegate=delegate
app.setActivationPolicy(.regular)
app.run()
