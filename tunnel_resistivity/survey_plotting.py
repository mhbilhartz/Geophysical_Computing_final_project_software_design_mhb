"""Basic completed-survey views, separate from the numerical backend."""
from matplotlib.colors import LogNorm
from matplotlib.figure import Figure
from matplotlib.patches import Circle
import numpy as np


def build_survey_figure(result):
    plan=result.plan;model=result.model;grid=plan.grid;p=plan.parameters
    fig=Figure(figsize=(12,4.4),layout='constrained')
    geometry,profile=fig.subplots(1,2)
    resistivity=1/model.conductivity
    low,high=float(resistivity.min()),float(resistivity.max())
    if high/low<1+1e-10:low,high=low/1.1,high*1.1
    image=geometry.imshow(resistivity,extent=(grid.x_min_m,grid.x_max_m,grid.height_m,0),
                          origin='upper',aspect='equal',cmap='viridis',norm=LogNorm(low,high))
    geometry.add_patch(Circle((p.center_x_m,p.depth_m),p.radius_m,fill=False,edgecolor='gray',linestyle='--'))
    geometry.scatter(plan.survey.electrode_positions_x_m,[0]*len(plan.survey.electrode_positions_x_m),
                     marker='v',color='red',s=15,clip_on=False)
    geometry.set(xlabel='World horizontal x (m)',ylabel='Depth z (m)',title='Resistivity model and physical electrode line')
    fig.colorbar(image,ax=geometry,label='Resistivity (Ω·m)')
    rows=result.data.records()
    for level in range(1,p.max_level+1):
        selected=[row for row in rows if row['level']==level]
        profile.plot([r['spread_center_x_m'] for r in selected],[r['apparent_resistivity_ohm_m'] for r in selected],
                      'o-',markersize=4,label=f'Level {level}')
    profile.axhline(p.host_resistivity,color='gray',linestyle='--',label='Homogeneous host')
    profile.axvline(p.center_x_m,color='gray',linewidth=.7,alpha=.5)
    profile.set(xlabel='Full electrode-spread midpoint x (m)',ylabel='Apparent resistivity (Ω·m)',
                title=f'{p.array_type}: completed forward measurements')
    profile.grid(alpha=.2);profile.legend(fontsize=8)
    fig.suptitle(f'Tunnel center ({p.center_x_m:g}, {p.depth_m:g}) m · radius {p.radius_m:g} m · '
                 f'host {p.host_resistivity:g} / tunnel {p.tunnel_resistivity:g} Ω·m')
    return fig


def _log_scale(values):
    low=max(float(np.min(values)),float(np.max(values))*1e-12,1e-300)
    high=max(float(np.max(values)),low)
    if high/low<1+1e-10:low,high=low/1.1,high*1.1
    return LogNorm(low,high)


def _electrode_markers(ax,electrodes):
    for label,x,color in (('A',electrodes.a_x_m,'red'),('B',electrodes.b_x_m,'blue'),
                           ('M',electrodes.m_x_m,'darkorange'),('N',electrodes.n_x_m,'purple')):
        ax.plot(x,0,marker='v' if label in ('A','B') else 'o',color=color,markersize=4,clip_on=False)
        ax.annotate(label,(x,0),xytext=(0,-9),textcoords='offset points',ha='center',va='top',
                    color=color,fontsize=8,bbox={'facecolor':'white','edgecolor':'none','alpha':.75,'pad':1})


def build_field_figure(field):
    """Four maps at y=0 for one physical source pair, with requested M/N labels."""
    from matplotlib.colors import Normalize, SymLogNorm
    s=field.solution;request=field.request;result=request.result
    p=result.plan.parameters;g=result.plan.grid;e=request.electrodes
    magnitude=np.hypot(s.jx,s.jz)
    vlim=max(float(np.max(abs(s.potential))),1e-12)
    delta_limit=max(float(np.max(abs(s.secondary_potential))),1e-12)
    fig=Figure(figsize=(12,8),layout='constrained');axes=fig.subplots(2,2)
    panels=((1/s.conductivity,'Resistivity (Ω·m)','viridis',_log_scale(1/s.conductivity)),
            (s.potential,'Electrical potential (V; symmetric-log colors)','RdBu_r',SymLogNorm(vlim*1e-3,vmin=-vlim,vmax=vlim)),
            (magnitude,'Current magnitude (A/m²; unit direction arrows)','magma',_log_scale(magnitude)),
            (s.secondary_potential,'Tunnel − homogeneous potential (V)','RdBu_r',Normalize(-delta_limit,delta_limit)))
    for ax,(values,label,cmap,norm) in zip(axes.flat,panels):
        values=np.maximum(values,norm.vmin) if isinstance(norm,LogNorm) else values
        image=ax.imshow(values,extent=(g.x_min_m,g.x_max_m,g.height_m,0),origin='upper',aspect='equal',cmap=cmap,norm=norm)
        fig.colorbar(image,ax=ax,label=label,extend='min' if ax is axes[1,0] and np.any(magnitude<norm.vmin) else 'neither')
        ax.set(xlabel='World horizontal x (m)',ylabel='Depth z (m)',title=label)
        ax.add_patch(Circle((p.center_x_m,p.depth_m),p.radius_m,fill=False,edgecolor='gray',linestyle='--'))
        _electrode_markers(ax,e)
    # Normalize arrows individually: their length is a display choice, never a
    # physical current magnitude. Positive Jz points down on the inverted axis.
    iz=slice(None,None,max(1,len(s.z)//15));ix=slice(None,None,max(1,len(s.x)//22))
    xx,zz=np.meshgrid(s.x[ix],s.z[iz]);mag=magnitude[iz,ix]
    valid=mag>max(float(magnitude.max())*1e-12,1e-300)
    u=np.divide(s.jx[iz,ix],mag,out=np.zeros_like(mag),where=valid)
    v=np.divide(s.jz[iz,ix],mag,out=np.zeros_like(mag),where=valid)
    length=max(g.width_m,g.height_m)/32
    axes[1,0].quiver(xx,zz,np.ma.array(u,mask=~valid),np.ma.array(v,mask=~valid),
                     angles='xy',scale_units='xy',scale=1/length,color='cyan',width=.0025)
    fig.suptitle(f'Measurement {request.measurement_index+1}: A={e.a_x_m:g}, B={e.b_x_m:g}, '
                 f'M={e.m_x_m:g}, N={e.n_x_m:g} m; I={e.current_a:g} A (A+, B−)\n'
                 f'Tunnel ({p.center_x_m:g}, {p.depth_m:g}) m, radius {p.radius_m:g} m; '
                 f'host/tunnel {p.host_resistivity:g}/{p.tunnel_resistivity:g} Ω·m; y=0',fontsize=11)
    return fig


def build_surface_figure(field):
    """Surface secondary potential using the same reconstruction as receivers."""
    from .receivers import _surface_components
    request=field.request;e=request.electrodes;s=field.solution;g=request.result.plan.grid
    x=np.linspace(g.x_min_m+s.dx/4,g.x_max_m-s.dx/4,401)
    valid=(abs(x-e.a_x_m)>s.dx*1e-8)&(abs(x-e.b_x_m)>s.dx*1e-8)
    x=x[valid]
    _,secondary=_surface_components(s,x)
    _,receivers=_surface_components(s,np.array([e.m_x_m,e.n_x_m]))
    fig=Figure(figsize=(10,3.6),layout='constrained');ax=fig.subplots()
    ax.plot(x,secondary,label='Tunnel − homogeneous surface potential')
    ax.scatter([e.m_x_m,e.n_x_m],receivers,color=['darkorange','purple'],zorder=3,label='Receivers M, N')
    for label,pos in (('A',e.a_x_m),('B',e.b_x_m)):
        ax.axvline(pos,color='gray',linewidth=.8,linestyle=':')
        ax.text(pos,.98,label,ha='center',va='top',transform=ax.get_xaxis_transform())
    for label,pos,value in zip(('M','N'),(e.m_x_m,e.n_x_m),receivers):
        ax.annotate(label,(pos,value),xytext=(4,6),textcoords='offset points')
    ax.axhline(0,color='gray',linewidth=.6)
    ax.set(xlabel='Surface x (m)',ylabel='Surface ΔV (V)',title=f'Measurement {request.measurement_index+1}: secondary receiver voltage '
           f'ΔVM − ΔVN = {field.measurement.secondary_voltage_v:.6g} V')
    ax.grid(alpha=.2);ax.legend(fontsize=8)
    return fig


def build_survey_map(result,measurement_index=None):
    """Uninterpolated survey data by midpoint/level; vertical axis is NOT depth."""
    from matplotlib.colors import Normalize, SymLogNorm
    rows=result.data.records();rho=np.array([r['apparent_resistivity_ohm_m'] for r in rows])
    relative=100*np.array([r['relative_apparent_resistivity_anomaly'] for r in rows])
    midpoint=np.array([r['spread_center_x_m'] for r in rows]);level=np.array([r['level'] for r in rows])
    if np.all(rho>0):rho_norm=_log_scale(rho);rho_cmap='viridis'
    else:
        limit=max(float(abs(rho).max()),1e-12)
        rho_norm=SymLogNorm(limit*.01,vmin=-limit,vmax=limit);rho_cmap='RdBu_r'
    limit=max(float(abs(relative).max()),1e-6)
    fig=Figure(figsize=(12,4.2),layout='constrained');axes=fig.subplots(1,2)
    for ax,values,norm,cmap,label in zip(axes,(rho,relative),(rho_norm,Normalize(-limit,limit)),
                    (rho_cmap,'RdBu_r'),('Apparent resistivity (Ω·m)','Apparent resistivity anomaly (%)')):
        collection=ax.scatter(midpoint,level,c=values,norm=norm,cmap=cmap,marker='s',s=75)
        colorbar=fig.colorbar(collection,ax=ax,label=label)
        if isinstance(norm,LogNorm):
            from matplotlib.ticker import FormatStrFormatter
            colorbar.set_ticks(np.geomspace(norm.vmin,norm.vmax,5))
            colorbar.formatter=FormatStrFormatter('%.4g');colorbar.update_ticks()
            colorbar.minorticks_off()
        if measurement_index is not None:
            ax.scatter([midpoint[measurement_index]],[level[measurement_index]],s=145,
                       marker='s',facecolors='none',edgecolors='black',linewidths=1.3)
        positions=result.plan.survey.electrode_positions_x_m
        ax.set(xlabel='Full electrode-spread midpoint x (m)',ylabel='Array spacing level (not depth)',
               xlim=(positions[0],positions[-1]),ylim=(float(level.max())+.5,float(level.min())-.5),title=label)
        ax.set_yticks(sorted(set(level)));ax.grid(alpha=.15)
    fig.suptitle('Measured configurations only: no interpolation, pseudo-depth or inversion\n'
                 'Outlined square = selected measurement')
    return fig
