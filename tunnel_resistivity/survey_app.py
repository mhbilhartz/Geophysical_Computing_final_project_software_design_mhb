"""Live Panel survey UI. Default entry: python -m panel serve app.py --show."""
import csv
import html
import io
import logging
import threading

import panel as pn

from .live import LatestOnlyRunner
from .fields import FieldRequest, SourceFieldCache, default_measurement_index, solve_field_request
from .survey_plotting import (build_survey_figure, build_field_figure, build_surface_figure, build_survey_map)
from .survey_simulation import PRESETS, SurveyParameters, plan_simulation, run_survey_plan

pn.extension()


class PanelScheduler:
    """Dispatch to the Bokeh document or notebook kernel's main event loop."""
    def __init__(self):
        current=pn.state.curdoc
        self.doc=current if current is not None and current.session_context is not None else None
        self.loop=None;self.closed=False
        if self.doc is None:
            try:
                from IPython import get_ipython
                kernel=getattr(get_ipython(),'kernel',None)
                self.loop=getattr(kernel,'io_loop',None)
            except ImportError:pass

    def dispatch(self,callback):
        if self.closed:return
        if self.doc is not None:self.doc.add_next_tick_callback(callback)
        elif self.loop is not None:self.loop.add_callback(callback)
        else:callback()  # Unattached, programmatic use; no server document to lock.

    def later(self,ms,callback):
        if self.doc is not None:return self.doc.add_timeout_callback(callback,ms)
        if self.loop is not None:return self.loop.call_later(ms/1000,callback)
        timer=threading.Timer(ms/1000,lambda:self.dispatch(callback));timer.daemon=True;timer.start()
        return timer

    def cancel(self,handle):
        if self.doc is not None:
            try:self.doc.remove_timeout_callback(handle)
            except ValueError:pass
        else:handle.cancel()

    def close(self):self.closed=True


def describe(result):
    p=result.plan.parameters;g=result.plan.grid
    return (f'{p.array_type}; {p.electrode_count} electrodes, pitch {p.electrode_spacing_m:g} m; '
            f'levels 1–{p.max_level}; I={p.current_a:g} A. '
            f'Tunnel ({p.center_x_m:g}, {p.depth_m:g}) m, radius {p.radius_m:g} m; '
            f'host/tunnel {p.host_resistivity:g}/{p.tunnel_resistivity:g} Ω·m. '
            f'Grid {g.nx}×{g.nz}; x={g.x_min_m:g}…{g.x_max_m:g} m, bottom {g.height_m:g} m.')


def measurement_table(result):
    columns=(('measurement_id','ID'),('level','Level'),('a_x_m','A (m)'),('b_x_m','B (m)'),
             ('m_x_m','M (m)'),('n_x_m','N (m)'),('voltage_v','VM−VN (V)'),
             ('geometric_factor_m','Signed K (m)'),('apparent_resistivity_ohm_m','ρa (Ω·m)'),
             ('relative_apparent_resistivity_anomaly','Relative anomaly'))
    header=''.join(f'<th style="padding:6px">{label}</th>' for _,label in columns)
    rows=[]
    for record in result.data.records():
        values=[]
        for key,_ in columns:
            value=record[key]
            text=f'{100*value:.3f}%' if key=='relative_apparent_resistivity_anomaly' else f'{value:.7g}'
            values.append(f'<td style="padding:6px;text-align:right">{html.escape(text)}</td>')
        rows.append('<tr>'+''.join(values)+'</tr>')
    return '<div style="overflow:auto;max-height:370px"><table><thead><tr>'+header+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'


class SurveySimulatorApp:
    """Per-session controls/results with debounced background source solves."""
    def __init__(self,*,initial_run=True,debounce_ms=400,scheduler=None,work=run_survey_plan,executor=None):
        self.latest=None;self.previous=None;self.run_number=0;self._updating=False;self._current_complete=False
        self.scheduler=scheduler or PanelScheduler()
        self.radius=pn.widgets.FloatSlider(label='Tunnel radius (m)',start=2,end=10,step=.5,value=5)
        self.depth=pn.widgets.FloatSlider(label='Tunnel center depth (m)',start=5.5,end=100,step=.5,value=15)
        self.center_x=pn.widgets.FloatSlider(label='Tunnel horizontal position (m)',start=-200,end=400,step=.5,value=50)
        self.host=pn.widgets.FloatInput(label='Background rock resistivity (Ω·m)',start=1,end=1e5,step=10,value=100)
        self.material=pn.widgets.Select(label='Tunnel material',options=[*PRESETS,'Custom'],value='Air-filled')
        self.tunnel=pn.widgets.FloatInput(label='Tunnel resistivity (Ω·m)',start=.1,end=1e8,step=1,value=1e8,disabled=True)
        self.array_type=pn.widgets.Select(label='Array type',options={'Wenner':'wenner','Schlumberger':'schlumberger','Dipole–dipole':'dipole-dipole'},value='wenner')
        self.electrode_count=pn.widgets.IntSlider(label='Number of physical electrodes',start=4,end=21,value=9)
        self.pitch=pn.widgets.FloatSlider(label='Electrode line spacing p (m)',start=1,end=10,step=.5,value=5)
        self.line_start=pn.widgets.FloatInput(label='First electrode x (m)',start=-100,end=100,step=5,value=30)
        self.levels=pn.widgets.IntSlider(label='Maximum spacing level',start=1,end=2,value=2)
        self.receiver_steps=pn.widgets.IntSlider(label='Schlumberger MN spacing / p',start=1,end=5,value=1,visible=False)
        self.dipole_steps=pn.widgets.IntSlider(label='Dipole length / p',start=1,end=3,value=1,visible=False)
        self.current=pn.widgets.FloatInput(label='Injected current I (A)',start=.0001,end=10,step=.05,value=.1)
        self.grid_mode=pn.widgets.Select(label='Grid/domain mode',options=['Automatic','Manual'],value='Automatic')
        self.resolution=pn.widgets.Select(label='Maximum cell size (m)',options={'Coarse: ≤1.25 m':1.25,'Medium: ≤0.8 m':.8,'Fine: ≤0.625 m':.625},value=1.25)
        self.padding=pn.widgets.FloatSlider(label='Automatic boundary padding / max spread',start=1,end=4,step=.5,value=2)
        self.x_min=pn.widgets.FloatInput(label='Left grid face x (m)',value=-30.,step=5)
        self.x_max=pn.widgets.FloatInput(label='Right grid face x (m)',value=130.,step=5)
        self.height=pn.widgets.FloatInput(label='Bottom depth (m)',start=1,value=80.,step=5)
        self.nx=pn.widgets.IntInput(label='Horizontal cells nx',start=2,end=2000,value=128)
        self.nz=pn.widgets.IntInput(label='Depth cells nz',start=2,end=2000,value=64)
        self.manual_controls=pn.Column(self.x_min,self.x_max,self.height,self.nx,self.nz,visible=False)
        self.reset_button=pn.widgets.Button(label='Reset to Defaults',color='primary',width=290)
        self.download=pn.widgets.FileDownload(label='Download displayed survey CSV',callback=self._csv,
                                              filename='survey.csv',disabled=True,width=290)
        self.status=pn.pane.Alert('Waiting for the initial automatic run.',alert_type='info')
        self.preview=pn.pane.Markdown('',sizing_mode='stretch_width')
        self.notes=pn.pane.Alert('',alert_type='warning',visible=False)
        self.latest_view=pn.Column('The first survey is computed automatically.',sizing_mode='stretch_width')
        self.previous_view=pn.Column('The previous completed survey will appear here.',sizing_mode='stretch_width')
        self.tabs=pn.Tabs(('Latest completed survey',self.latest_view),('Previous survey',self.previous_view),
                          dynamic=True,sizing_mode='stretch_width')
        self.runner=LatestOnlyRunner(work,self.scheduler,on_result=self._publish,on_error=self._error,
                                     on_progress=self._progress,debounce_ms=debounce_ms,executor=executor)
        self._field_updating=False;self._field_selection={};self._field_cache=SourceFieldCache(2)
        self.field_latest=None;self._field_figure=None
        self.measurement=pn.widgets.Select(label='Inspect measurement from displayed survey',options={},disabled=True,
                                          sizing_mode='stretch_width',css_classes=['sim-measurement'])
        self.field_status=pn.pane.Alert('Field views will follow the first completed survey.',alert_type='info',
                                       css_classes=['sim-field_status'])
        self.field_info=pn.pane.Markdown('',sizing_mode='stretch_width')
        self.field_download=pn.widgets.FileDownload(label='Download selected field PNG',callback=self._field_png,
                              filename='selected_fields.png',disabled=True,css_classes=['sim-field_download'])
        self.field_view=pn.Column('Choose a completed measurement to inspect its fields.',sizing_mode='stretch_width')
        self.surface_view=pn.Column('Surface differences appear with the selected fields.',sizing_mode='stretch_width')
        self.map_view=pn.Column('Survey maps appear after a completed run.',sizing_mode='stretch_width')
        self.explorer_tabs=pn.Tabs(('Potential and current fields',self.field_view),('Surface potential difference',self.surface_view),
                         ('Survey configuration map',self.map_view),dynamic=True,sizing_mode='stretch_width',
                         css_classes=['sim-explorer_tabs'])
        self.explorer=pn.Column('### Explore fields and survey configurations',self.measurement,self.field_status,self.field_info,
                     self.field_download,self.explorer_tabs,sizing_mode='stretch_width',css_classes=['sim-explorer'])
        self.field_runner=LatestOnlyRunner(solve_field_request,self.scheduler,on_result=self._publish_fields,
                      on_error=self._field_error,on_progress=lambda done,total:None,debounce_ms=200)
        controls=pn.Column(pn.Accordion(
            ('Tunnel and host',pn.Column(self.material,self.tunnel,self.host,self.radius,self.depth,self.center_x)),
            ('Electrode survey',pn.Column(self.array_type,self.electrode_count,self.pitch,self.line_start,self.levels,
                                         self.receiver_steps,self.dipole_steps,self.current)),
            ('Grid and domain',pn.Column(self.grid_mode,self.resolution,self.padding,self.manual_controls)),
            active=[0,1],sizing_mode='stretch_width'),self.reset_button,self.download,width=320)
        self.view=pn.Column(
            '# Electrical Resistivity Survey Forward Modeler',
            '2.5D DC point electrodes with a circular tunnel extending along the cross-line direction. '
            '**Changes run automatically—no Run button.** Brief pauses in slider movement start a new calculation.',
            pn.Row(controls,pn.Column(self.status,self.preview,self.notes,self.tabs,self.explorer,min_width=620,sizing_mode='stretch_width'),
                   sizing_mode='stretch_width'),
            '**Read the results:** apparent resistivity profiles are forward measurements, not an inverted depth image. '
            'Levels mean Wenner a/p, Schlumberger A–M gap/p, and dipole–dipole n. '
            'Source electrodes inject +I at A and −I at B; receiver voltage is VM−VN. '
            'Outer walls use the analytical primary; the surface is insulating away from point electrodes. '
            'Compare grid/domain sensitivity before interpreting a tunnel anomaly.',
            sizing_mode='stretch_width')
        self._widgets=(self.radius,self.depth,self.center_x,self.host,self.material,self.tunnel,self.array_type,
                       self.electrode_count,self.pitch,self.line_start,self.levels,self.receiver_steps,self.dipole_steps,
                       self.current,self.grid_mode,self.resolution,self.padding,self.x_min,self.x_max,self.height,self.nx,self.nz)
        for name in ('radius','depth','center_x','host','material','tunnel','array_type','electrode_count',
                     'pitch','line_start','levels','receiver_steps','dipole_steps','current','grid_mode',
                     'resolution','padding','x_min','x_max','height','nx','nz','reset_button','download',
                     'status','preview','latest_view'):
            getattr(self,name).css_classes=[f'sim-{name}']
        for widget in self._widgets:widget.param.watch(self._changed,'value')
        self.reset_button.on_click(self.reset)
        self.tabs.param.watch(self._tab_changed,'active')
        self.measurement.param.watch(self._measurement_changed,'value')
        self._sync_controls()
        doc=getattr(self.scheduler,'doc',None)
        if doc is not None:doc.on_session_destroyed(lambda context:self.close())
        if initial_run:self._changed()

    def _sync_controls(self):
        self._updating=True
        try:
            self.tunnel.disabled=self.material.value!='Custom'
            if self.material.value in PRESETS:self.tunnel.value=PRESETS[self.material.value]
            minimum=float(self.radius.value)+.5
            self.depth.param.update(start=minimum,value=max(minimum,self.depth.value))
            count=self.electrode_count.value
            receiver_max=min(5,count-3);dipole_max=min(3,(count-1)//3)
            self.receiver_steps.end=max(2,receiver_max)
            self.receiver_steps.value=min(self.receiver_steps.value,receiver_max)
            self.receiver_steps.disabled=receiver_max==1
            self.dipole_steps.end=max(2,dipole_max)
            self.dipole_steps.value=min(self.dipole_steps.value,dipole_max)
            self.dipole_steps.disabled=dipole_max==1
            kind=self.array_type.value
            self.receiver_steps.visible=kind=='schlumberger';self.dipole_steps.visible=kind=='dipole-dipole'
            maximum=((count-1)//3 if kind=='wenner' else
                     (count-1-self.receiver_steps.value)//2 if kind=='schlumberger' else
                     (count-1)//self.dipole_steps.value-2)
            maximum=max(1,min(8,maximum))
            self.levels.param.update(end=max(2,maximum),value=min(self.levels.value,maximum),disabled=maximum==1)
            manual=self.grid_mode.value=='Manual'
            self.manual_controls.visible=manual;self.resolution.visible=self.padding.visible=not manual
        finally:self._updating=False

    def parameters(self):
        return SurveyParameters(array_type=self.array_type.value,electrode_count=self.electrode_count.value,
            electrode_spacing_m=self.pitch.value,line_start_x_m=self.line_start.value,max_level=self.levels.value,
            receiver_spacing_steps=self.receiver_steps.value if self.array_type.value=='schlumberger' else 1,
            dipole_spacing_steps=self.dipole_steps.value if self.array_type.value=='dipole-dipole' else 1,
            current_a=self.current.value,depth_m=self.depth.value,radius_m=self.radius.value,center_x_m=self.center_x.value,
            host_resistivity=self.host.value,tunnel_resistivity=PRESETS.get(self.material.value,self.tunnel.value),
            grid_mode=self.grid_mode.value,max_cell_size_m=self.resolution.value,padding_factor=self.padding.value,
            x_min_m=self.x_min.value,x_max_m=self.x_max.value,height_m=self.height.value,nx=self.nx.value,nz=self.nz.value)

    def _changed(self,event=None):
        if self._updating or self.runner.closed:return
        self._current_complete=False
        self._clear_fields('Controls changed. Field views wait for the new completed survey.')
        self.download.disabled=True
        try:
            self._sync_controls()
            plan=plan_simulation(self.parameters())
        except (ValueError,TypeError,OverflowError) as exc:
            self.preview.object='**Requested plan is invalid.** Displayed results, if any, describe the last completed survey.'
            self.runner.invalidate();self._error(exc);return
        g=plan.grid
        self.preview.object=(f'**Requested plan:** {len(plan.survey.measurements)} measurements; '
            f'{plan.survey.unique_source_pair_count} source solves × 64 Fourier modes. '
            f'Grid **{g.nx} × {g.nz}** ({g.cell_count:,} cells), dx={g.dx_m:.3g} m, dz={g.dz_m:.3g} m; '
            f'x={g.x_min_m:g}…{g.x_max_m:g} m; bottom={g.height_m:g} m.')
        self.runner.request(plan)
        self.status.alert_type='info'
        self.status.object='Changes queued automatically. Any displayed data still belong to the labeled last completed survey.'

    def _progress(self,done,total):
        self.status.alert_type='info'
        self.status.object=f'Computing requested survey: {done}/{total} source solves completed. Controls remain active; older displayed data are labeled below.'

    def _error(self,exc):
        self._current_complete=False
        self._clear_fields('The current request is invalid or failed. Completed survey data are retained above.')
        self.status.alert_type='danger'
        self.status.object=f'Survey not updated: {exc}. Last completed results are retained.'
        self.download.disabled=True
        if not isinstance(exc,(ValueError,RuntimeError,TypeError,OverflowError)):
            logging.getLogger(__name__).error('Unexpected survey failure',exc_info=(type(exc),exc,exc.__traceback__))

    def _publish(self,result):
        try:
            fig=build_survey_figure(result)
            number=self.run_number+1
            diagnostics=(f'**Numerical diagnostics:** max relative mode residual '
                f'{result.data.max_relative_mode_residual:.2e}; mode balance '
                f'{result.data.max_relative_mode_balance_error:.2e}. '
                f'{result.data.solve_count} source solves in {result.data.elapsed_seconds:.2f} s. '
                'Small residuals do not certify mesh or boundary accuracy.')
            contents=[pn.pane.Markdown(f'### Completed survey {number}\n{describe(result)}'),
                      pn.pane.Matplotlib(fig,format='png',dpi=110,tight=False,sizing_mode='stretch_width'),
                      pn.pane.Markdown(diagnostics),pn.pane.HTML(measurement_table(result),sizing_mode='stretch_width')]
        except Exception as exc:self._error(exc);return
        if self.latest is not None:self.previous_view.objects=list(self.latest_view.objects)
        self.previous,self.latest=self.latest,result;self.run_number=number
        self.latest_view.objects=contents;self.tabs.active=0
        self.notes.object='\n\n'.join(result.model.warnings);self.notes.visible=bool(result.model.warnings)
        self.status.alert_type='success'
        self.status.object=f'Survey {number} complete. Displayed data match the requested parameters. Further changes rerun automatically.'
        self._current_complete=True;self._update_download()
        self._field_cache.retain((self.latest,self.previous))
        allowed={id(item) for item in (self.latest,self.previous) if item is not None}
        self._field_selection={key:value for key,value in self._field_selection.items() if key in allowed}
        self._update_field_selection()

    def _tab_changed(self,event):
        self._update_download();self._update_field_selection()

    def _clear_fields(self,message):
        self.field_runner.invalidate();self.field_latest=None;self._field_figure=None
        self.field_download.disabled=True;self.measurement.disabled=True
        self.field_info.object=''
        self.field_status.alert_type='info';self.field_status.object=message
        self.field_view.objects=[message];self.surface_view.objects=[message];self.map_view.objects=[message]

    def _update_field_selection(self):
        result=self._selected_result()
        if not self._current_complete or result is None:
            self._clear_fields('Choose a completed survey after the current request finishes.');return
        options={}
        for i,entry in enumerate(result.plan.survey.measurements):
            e=entry.electrodes
            options[f'#{i+1} · level {entry.level} · A {e.a_x_m:g}, B {e.b_x_m:g}, M {e.m_x_m:g}, N {e.n_x_m:g} m']=i
        selected=self._field_selection.get(id(result),default_measurement_index(result))
        self._field_updating=True
        try:self.measurement.param.update(options=options,value=selected,disabled=False)
        finally:self._field_updating=False
        self._measurement_changed()

    def _measurement_changed(self,event=None):
        if self._field_updating:return
        result=self._selected_result()
        if not self._current_complete or result is None or self.measurement.value is None:return
        index=self.measurement.value;self._field_selection[id(result)]=index
        self._clear_fields('Calculating the selected source field. Old field images are hidden until it completes.')
        self.measurement.disabled=False
        number=self.run_number-(1 if self.tabs.active==1 else 0)
        self.field_info.object=f'**Fields for completed survey {number}, measurement {index+1}.** {describe(result)}'
        self.map_view.objects=[pn.pane.Matplotlib(build_survey_map(result,index),format='png',dpi=110,
                                                tight=False,sizing_mode='stretch_width')]
        request=FieldRequest(result,index)
        cached=self._field_cache.get(request)
        if cached is not None:self._publish_fields(cached)
        else:self.field_runner.request(request)

    def _field_error(self,exc):
        self.field_status.alert_type='danger';self.field_status.object=f'Selected field was not updated: {exc}'
        self.field_download.disabled=True

    def _publish_fields(self,field):
        if (not self._current_complete or self._selected_result() is not field.request.result
                or self.measurement.value!=field.request.measurement_index):return
        try:
            figure=build_field_figure(field);surface=build_surface_figure(field)
            panes=[pn.pane.Matplotlib(figure,format='png',dpi=110,tight=False,sizing_mode='stretch_width'),
                   pn.pane.Markdown('Arrows show direction only; the logarithmic color bar shows current magnitude. '
                   'Potential uses symmetric-log colors; ΔV uses a zero-centered linear scale. '
                   'Cell-center currents are approximate at conductivity jumps.')]
            self.field_view.objects=panes
            self.surface_view.objects=[pn.pane.Matplotlib(surface,format='png',dpi=110,tight=False,sizing_mode='stretch_width')]
        except Exception as exc:self._field_error(exc);return
        self.field_latest=field;self._field_figure=figure;self._field_cache.put(field)
        self.field_status.alert_type='success'
        self.field_status.object=f'Fields ready for measurement {field.request.measurement_index+1}. Grid, sources and reference match its completed survey.'
        self.field_download.filename=f'fields_survey_{self.run_number-(1 if self.tabs.active==1 else 0)}_measurement_{field.request.measurement_index+1}.png'
        self.field_download.disabled=False

    def _field_png(self):
        if self._field_figure is None:raise ValueError('No completed selected field image')
        output=io.BytesIO();self._field_figure.savefig(output,format='png',dpi=160);output.seek(0)
        return output

    def _selected_result(self):
        return self.previous if self.tabs.active==1 else self.latest

    def _update_download(self):
        selected=self._selected_result()
        self.download.disabled=not (self._current_complete and selected is not None)
        if selected is not None:
            number=self.run_number-(1 if self.tabs.active==1 else 0)
            self.download.filename=f'survey_{number}_{selected.plan.parameters.array_type}.csv'

    def _csv(self):
        selected=self._selected_result()
        if selected is None:raise ValueError('No completed survey in the selected tab')
        rows=selected.data.records();text=io.StringIO()
        p=selected.plan.parameters
        for row in rows:
            row.update(tunnel_center_x_m=p.center_x_m,tunnel_depth_m=p.depth_m,tunnel_radius_m=p.radius_m,
                       host_resistivity_ohm_m=p.host_resistivity,tunnel_resistivity_ohm_m=p.tunnel_resistivity,
                       physical_electrode_count=p.electrode_count,physical_electrode_spacing_m=p.electrode_spacing_m,
                       first_electrode_x_m=p.line_start_x_m,max_spacing_level=p.max_level,
                       receiver_spacing_steps=p.receiver_spacing_steps,dipole_spacing_steps=p.dipole_spacing_steps,
                       grid_mode=p.grid_mode)
        writer=csv.DictWriter(text,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        return io.BytesIO(text.getvalue().encode('utf-8'))

    def reset(self,event=None):
        self._updating=True
        try:
            defaults=SurveyParameters()
            self.material.value='Air-filled'
            for widget,name in ((self.radius,'radius_m'),(self.depth,'depth_m'),(self.center_x,'center_x_m'),
                                (self.host,'host_resistivity'),(self.tunnel,'tunnel_resistivity'),
                                (self.array_type,'array_type'),(self.electrode_count,'electrode_count'),
                                (self.pitch,'electrode_spacing_m'),(self.line_start,'line_start_x_m'),
                                (self.current,'current_a'),(self.grid_mode,'grid_mode'),(self.resolution,'max_cell_size_m'),
                                (self.padding,'padding_factor'),(self.x_min,'x_min_m'),(self.x_max,'x_max_m'),
                                (self.height,'height_m'),(self.nx,'nx'),(self.nz,'nz')):
                widget.value=getattr(defaults,name)
            # Restore bounds before values that might have been narrowed.
            self.receiver_steps.end=5;self.dipole_steps.end=3;self.levels.end=8
            self.receiver_steps.value=self.dipole_steps.value=1;self.levels.value=2
        finally:self._updating=False
        self._changed()

    def close(self):
        self.runner.close()
        self.field_runner.close();self._field_cache.clear()
        if hasattr(self.scheduler,'close'):self.scheduler.close()


def create_app():
    """A separate live controller for each browser/notebook session."""
    return SurveySimulatorApp().view
