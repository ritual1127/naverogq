import win32com.client as w32

app = w32.Dispatch("Inventor.Application")
app.Visible = False
print("OK  SoftwareVersion:", app.SoftwareVersion.DisplayName)
print("OK  Visible:", app.Visible)
print("OK  Documents.Count:", app.Documents.Count)
print("OK  DesignProjectName:", app.DesignProjectManager.ActiveDesignProject.Name)

