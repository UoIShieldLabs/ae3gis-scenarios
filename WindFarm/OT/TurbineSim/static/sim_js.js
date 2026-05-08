async function update(){
  let r = await fetch('/api/state')
  let data = await r.json()
  for (const [k,v] of Object.entries(data)){
    document.getElementById(k).innerText=v.toFixed(3)
  }
}

async function setWind(){
  let val=document.getElementById("wind_input").value
    await fetch('/api/set_wind',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      speed:parseFloat(val)
    })
  })
}

async function upload(){
  let file=document.getElementById("file").files[0]
  let form=new FormData()
  form.append("file",file)
  await fetch('/api/upload_wind',{
    method:'POST',
    body:form
  })
}

async function generatePlot(){
  let r = await fetch(`/api/plot_sim?time=${new Date().getTime()}`)
  let blob = await r.blob();
  // document.getElementById("plot_image").src=r
  document.getElementById("plot_image").src = URL.createObjectURL(blob);
  document.getElementById("download_btn").disabled=false
}

function downloadPlot(){
  // window.location="/download_plot"
  const a = document.createElement('a');
  
  // Use a relative path (no leading slash) to respect the proxy URL
  a.href = 'download_plot'; 
  
  // Trigger the download without navigating the window
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}


setInterval(update,500)