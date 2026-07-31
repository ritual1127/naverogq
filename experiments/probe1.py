"""Probe 1: can we drive Inventor headlessly at all?"""
import win32com.client as w32

app = w32.Dispatch("Inventor.Application")
app.Visible = False
print("OK  SoftwareVersion:", app.SoftwareVersion.DisplayName)
print("OK  Visible:", app.Visible)
print("OK  Documents.Count:", app.Documents.Count)
print("OK  DesignProjectName:", app.DesignProjectManager.ActiveDesignProject.Name)
# do NOT quit: leave it warm for the next probe, quitting is slow
