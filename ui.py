streamlit.errors.StreamlitValueBelowMinError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).

Traceback:
File "/mount/src/estimateur-facade-libertv2/app.py", line 667, in <module>
    main()
    ~~~~^^
File "/mount/src/estimateur-facade-libertv2/app.py", line 405, in main
    dims = ui.render_map_and_form(GOOGLE_API_KEY, ui.render_building_dimensions_form, osm_ctx)
File "/mount/src/estimateur-facade-libertv2/ui.py", line 110, in render_map_and_form
    out = form_func(osm_ctx or {}, **form_kwargs)
File "/mount/src/estimateur-facade-libertv2/ui.py", line 159, in render_building_dimensions_form
    profondeur = st.number_input(
        "Profondeur approximative du bâtiment (m)",
    ...<4 lines>...
        help="Utilisé pour un éventuel pignon ou un pavillon complet.",
    )
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/runtime/metrics_util.py", line 447, in wrapped_func
    result = non_optional_func(*args, **kwargs)
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/elements/widgets/number_input.py", line 399, in number_input
    return self._number_input(
           ~~~~~~~~~~~~~~~~~~^
        label=label,
        ^^^^^^^^^^^^
    ...<15 lines>...
        ctx=ctx,
        ^^^^^^^^
    )
    ^
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/elements/widgets/number_input.py", line 542, in _number_input
    raise StreamlitValueBelowMinError(value=value, min_value=min_value)
