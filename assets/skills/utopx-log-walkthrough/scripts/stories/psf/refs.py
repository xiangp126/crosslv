"""The source lines the PSF story cites, found by their code in the trees the run used (wt/coderefs.py). The story text
names one as [[ref:<name>]]; [[tree:<repo>]] is the run's commit of that repository."""
from wt.coderefs import CodeRef

CODEREFS = {
    # golan_fw: the pool reclaim in TEARDOWN_HCA, the global-mode branch of psf_teardown_hca(), the pre-init DISABLE_HCA
    'psf_pool_reclaim': CodeRef('golan_fw', 'src/main/page_supplier_func.c',
                                r'^static void psf_pool_handle_teardown_hca_reclaim\(void\)', end=r'^\}'),
    'psf_teardown_global': CodeRef('golan_fw', 'src/main/page_supplier_func.c', r'^    if \(is_icm_mng_global_mode_enabled\(\)\) \{',
                                   end=r'^    \}', within=r'^uint32 psf_teardown_hca\('),
    'disable_hca_psf_pre_init': CodeRef('golan_fw', 'src/main/icm_access_layer.c',
                                        r'is_gvmi_psf\(gvmi\) && \(HCA_STATE_PRE_INIT_ICM_DONE == toc->hca_state\)', end=3),
    # utopx: the reclaim request and its op_mod, the contiguity check and the one PAS entry of a range, the random draws
    'reclaim_request': CodeRef('utopx', 'src/hca/CmdManagePages.cpp', r'SetReqPages\(pageManager->GetNumPagesProvided\(\)\s*\*\s*-1\)'),
    'reclaim_op_mod': CodeRef('utopx', 'src/hca/CmdManagePages.cpp', r'in->op_mod = \(req_pages < 0\) \? RECLAIM_PAGES : PROVIDE_PAGES;'),
    'range_contiguous': CodeRef('utopx', 'src/hca/CmdManagePages.cpp', r'UFATAL_IF\("PROVIDE_PAGES_RANGE pages are not contiguous"'),
    'range_first_page': CodeRef('utopx', 'src/hca/CmdManagePages.cpp', r'pages\.resize\(1\);'),
    'range_count_random': CodeRef('utopx', 'src/hca/CmdManagePages.cpp', r'in->input_num_entries = GenUint32\(1, numPagesLeft\);'),
    'pool_size_conf': CodeRef('utopx', 'config/common_constraints.conf', r'^icm_mng_global_keeps\.total_icm_pages_to_allocate\s*='),
}
