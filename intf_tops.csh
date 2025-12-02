#!/bin/tcsh -f
# generate interferograms for tops stacks
# used for time series analysis
# Xiaohua(Eric) Xu, Jan 20 2016

if ($#argv != 2) then
  echo ""
  echo "Usage: intf_tops.csh intf.in batch_tops.config"
  echo ""
  exit 1
endif

if (! -f $1) then
  echo "no input file: $1"
  exit 1
endif

if (! -f $2) then
  echo "no config file: $2"
  exit 1
endif

# Read parameters from config
set stage = `awk '/proc_stage/ {print $3}' $2`
set master = `awk '/master_image/ {print $3}' $2`
set filter = `awk '/filter_wavelength/ {print $3}' $2`
if ("x$filter" == "x") then
  set filter = 200
  echo ""
  echo "WARNING: filter_wavelength not set, using default 200"
endif
set dec = `awk '/dec_factor/ {print $3}' $2`
set topo_phase = `awk '/topo_phase/ {print $3}' $2`
set shift_topo = `awk '/shift_topo/ {print $3}' $2`
set threshold_snaphu = `awk '/threshold_snaphu/ {print $3}' $2`
set threshold_geocode = `awk '/threshold_geocode/ {print $3}' $2`
set region_cut = `awk '/region_cut/ {print $3}' $2`
set switch_land = `awk '/switch_land/ {print $3}' $2`
set defomax = `awk '/defomax/ {print $3}' $2`
set range_dec = `awk '/range_dec/ {print $3}' $2`
set azimuth_dec = `awk '/azimuth_dec/ {print $3}' $2`
set near_interp = `awk '/near_interp/ {print $3}' $2`
set mask_water = `awk '/mask_water/ {print $3}' $2`

# ------------------------
# 1 - DEM and topo_phase
# ------------------------
if ($stage <= 1) then
  cleanup.csh topo
  if ($topo_phase == 1) then
    echo ""
    echo "DEM2TOPOPHASE.CSH - START"
    cd topo
    cp ../raw/$master.PRM master.PRM
    ln -s ../raw/$master.LED .

    if (-f dem.grd) then
      if ("x$region_cut" == "x") then
        dem2topo_ra.csh master.PRM dem.grd
      else
        cut_slc master.PRM junk $region_cut 1
        mv junk.PRM master.PRM
        dem2topo_ra.csh master.PRM dem.grd
      endif
    else
      echo "no DEM file found: dem.grd"
      exit 1
    endif

    if ($shift_topo == 1) then
      echo "OFFSET_TOPO - START"
      ln -s ../raw/$master.SLC .
      slc2amp.csh master.PRM 4 amp-$master.grd
      offset_topo amp-$master.grd topo_ra.grd 0 0 7 topo_shift.grd
      echo "OFFSET_TOPO - END"
    else if ($shift_topo == 0) then
      echo "NO TOPOPHASE SHIFT"
    else
      echo "Wrong parameter: shift_topo = $shift_topo"
      exit 1
    endif
    cd ..
    echo "DEM2TOPOPHASE.CSH - END"
  else if ($topo_phase == 0) then
    echo "NO TOPOPHASE IS SUBTRACTED"
  else
    echo "Wrong parameter: topo_phase = $topo_phase"
    exit 1
  endif
endif

# ------------------------
# 2 - Create Interferograms
# ------------------------
if ($stage <= 2) then
  echo ""
  echo "START FORMING A STACK OF INTERFEROGRAMS"
  mkdir -p intf
  mkdir -p intf_all

  set fp = $1
  set fid = `mktemp`
  cat $fp >! $fid
  set i = 1
  set n = `wc -l < $fid`
  @ n = $n

  while ($i <= $n)
    set line = `sed -n "${i}p" $fid`
    set ref = `echo "$line" | awk -F: '{print $1}'`
    set rep = `echo "$line" | awk -F: '{print $2}'`
    set ref_id = `grep SC_clock_start ./raw/$ref.PRM | awk '{printf("%d",int($3))}'`
    set rep_id = `grep SC_clock_start ./raw/$rep.PRM | awk '{printf("%d",int($3))}'`

    echo ""
    echo "INTF.CSH, FILTER.CSH - START"
    cd intf
    mkdir ${ref_id}_${rep_id}
    cd ${ref_id}_${rep_id}
    ln -s ../../raw/$ref.LED .
    ln -s ../../raw/$rep.LED .
    ln -s ../../raw/$ref.SLC .
    ln -s ../../raw/$rep.SLC .
    cp ../../raw/$ref.PRM .
    cp ../../raw/$rep.PRM .

    if ("x$region_cut" != "x") then
      echo "Cutting SLC image to $region_cut"
      cut_slc $ref.PRM junk1 $region_cut
      cut_slc $rep.PRM junk2 $region_cut
      mv junk1.PRM $ref.PRM 
      mv junk2.PRM $rep.PRM
      mv junk1.SLC $ref.SLC
      mv junk2.SLC $rep.SLC
    endif

    if ($topo_phase == 1) then
      if ($shift_topo == 1) then
        ln -s ../../topo/topo_shift.grd .
        intf.csh $ref.PRM $rep.PRM -topo topo_shift.grd
      else
        ln -s ../../topo/topo_ra.grd .
        intf.csh $ref.PRM $rep.PRM -topo topo_ra.grd
      endif
    else
      intf.csh $ref.PRM $rep.PRM
    endif

    filter.csh $ref.PRM $rep.PRM $filter $dec $range_dec $azimuth_dec
    echo "INTF.CSH, FILTER.CSH - END"

    if ($threshold_snaphu != 0) then
      if ($mask_water == 1 || $switch_land == 1) then
        set mask_region = `gmt grdinfo phase.grd -I- | cut -c3-20`
        cd ../../topo
        if (! -f landmask_ra.grd) then
          landmask.csh $mask_region
        endif
        cd ../intf/${ref_id}_${rep_id}
        ln -s ../../topo/landmask_ra.grd .
      endif

      echo ""
      echo "SNAPHU.CSH - START"
      if ($near_interp == 1) then
        snaphu_interp.csh $threshold_snaphu $defomax
      else
        snaphu.csh $threshold_snaphu $defomax
      endif
      echo "SNAPHU.CSH - END"
    else
      echo "SKIP UNWRAP PHASE"
    endif

    echo ""
    echo "GEOCODE.CSH - START"
    if ($topo_phase == 1 && $threshold_geocode != 0) then
      rm -f raln.grd ralt.grd trans.dat
      ln -s ../../topo/trans.dat .
      geocode.csh $threshold_geocode
    else if ($topo_phase == 1 && $threshold_geocode == 0) then
      echo "SKIP GEOCODING"
    else
      echo "topo_ra is needed to geocode"
      exit 1
    endif

    cd ../..
    if (-e intf_all/${ref_id}_${rep_id}) rm -rf intf_all/${ref_id}_${rep_id}
    mv intf/${ref_id}_${rep_id} intf_all/${ref_id}_${rep_id}

    @ i++
  end

  rm -f $fid
endif

echo ""
echo "END STACK OF TOPS INTERFEROGRAMS"
echo ""
