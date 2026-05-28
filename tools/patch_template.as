// ============================================================================
// SEIKIOS — Universal Inkagames Terrain Walkability Patch
// Template parameterized by tools/patch_inkagame.py
//
// Placeholders (substituted at patch-injection time):
//   {{ORIG_INIT}}      — original frame_1 DoAction content (usually `xyz1 = false;` or `xyz2 = false;`)
//   {{CHECK_FN}}       — global check function (Spongebob: xyz163, Bart: xyz141, Lisa: xyz161)
//   {{OBJ_SCENE}}      — _root.<name> objScene (Spongebob: xyz113, Bart: xyz283, Lisa: xyz111)
//   {{SCENE_CLIP}}     — objScene.<name> scene MovieClip (Spongebob: xyz124, Bart: xyz309, Lisa: xyz122)
//   {{TERRAIN_ARRAY}}  — objScene.<name> 2D walkability array (Spongebob: xyz1374, Bart: xyz1175, Lisa: xyz1371)
//   {{RECT}}           — objScene.<name> rect with xMin/yMin (Spongebob: xyz1375, Bart: xyz1179, Lisa: xyz1372)
//   {{CELL_W_REF}}     — full ref to cellWidth, e.g. "_loc6_.xyz1392" or "_root.xyz1243"
//   {{CELL_H_REF}}     — full ref to cellHeight, e.g. "_loc6_.xyz1393" or "_root.xyz1244"
//   {{REBUILD_CELL_W}} — full ref to cellWidth in _rebuildTerrain scope (objScene var = _loc2_…), e.g. "_root.{{OBJ_SCENE}}.xyz1392" or "_root.xyz1243"
//   {{REBUILD_CELL_H}} — same for cellHeight
//
// NOTE: _rebuildTerrain uses "add-only" semantics — it only marks cells as
// walkable (= 1) when hitTest passes, NEVER removes walkability from cells
// the original game marked as walkable. This is critical for cinematics:
// some games (Homer) have cinematic sequences that rely on specific cells
// being walkable per the original array, even if Ruffle's hitTest disagrees.
// Removing walkability via `arr[i][j] = undefined` was breaking Homer's
// bowling-ball-at-Death cinematic. Discovered via xyz105 bypass var in Homer's
// xyz152 function (each game has a different bypass var: xyz103 in Spongebob,
// xyz101 in Lisa, xyz105 in Homer).
// ============================================================================
{{ORIG_INIT}}
_root._installWalkableFix = function()
{
   if(_root.{{CHECK_FN}}_orig != undefined)
   {
      return undefined;
   }
   if(_root.{{CHECK_FN}} == undefined)
   {
      return undefined;
   }
   _root.{{CHECK_FN}}_orig = _root.{{CHECK_FN}};
   _root.{{CHECK_FN}} = function(arr, row, col)
   {
      var _loc5_ = _root.{{CHECK_FN}}_orig(arr,row,col);
      if(_loc5_)
      {
         return true;
      }
      var _loc6_ = _root.{{OBJ_SCENE}};
      if(_loc6_ == undefined || _loc6_.{{SCENE_CLIP}} == undefined)
      {
         return false;
      }
      var _loc7_ = _loc6_.{{SCENE_CLIP}}.mcWalkRange;
      if(_loc7_ == undefined)
      {
         return false;
      }
      var _loc8_ = _loc6_.{{RECT}};
      var _loc9_ = {{CELL_W_REF}};
      var _loc10_ = {{CELL_H_REF}};
      var _loc11_ = new Object();
      _loc11_.x = _loc8_.xMin + col * _loc9_ + _loc9_ / 2;
      _loc11_.y = _loc8_.yMin + row * _loc10_ + _loc10_ / 2;
      _loc6_.{{SCENE_CLIP}}.localToGlobal(_loc11_);
      if(_loc7_.hitTest(_loc11_.x,_loc11_.y,true))
      {
         arr[row][col] = 1;
         return true;
      }
      return false;
   };
};
_walkFixMc = _root.createEmptyMovieClip("_walkFixMc",_root.getNextHighestDepth());
_walkFixMc.onEnterFrame = function()
{
   _root._installWalkableFix();
   if(_root.{{CHECK_FN}}_orig != undefined)
   {
      delete this.onEnterFrame;
   }
};
_root._rebuildTerrain = function()
{
   var _loc2_ = _root.{{OBJ_SCENE}}.{{TERRAIN_ARRAY}};
   var _loc3_ = _root.{{OBJ_SCENE}}.{{RECT}};
   var _loc4_ = {{REBUILD_CELL_W}};
   var _loc5_ = {{REBUILD_CELL_H}};
   var _loc6_ = _root.{{OBJ_SCENE}}.{{SCENE_CLIP}}.mcWalkRange;
   if(_loc2_ == undefined || _loc6_ == undefined)
   {
      return undefined;
   }
   var _loc7_ = _loc2_.length;
   var _loc8_ = _loc2_[0].length;
   var _loc9_ = 0;
   var _loc10_ = 0;
   var _loc11_;
   while(_loc9_ < _loc7_)
   {
      _loc10_ = 0;
      while(_loc10_ < _loc8_)
      {
         _loc11_ = new Object();
         _loc11_.x = _loc3_.xMin + _loc10_ * _loc4_ + _loc4_ / 2;
         _loc11_.y = _loc3_.yMin + _loc9_ * _loc5_ + _loc5_ / 2;
         _root.{{OBJ_SCENE}}.{{SCENE_CLIP}}.localToGlobal(_loc11_);
         if(_loc6_.hitTest(_loc11_.x,_loc11_.y,true))
         {
            if(_loc2_[_loc9_][_loc10_] != 1)
            {
               _loc2_[_loc9_][_loc10_] = 1;
            }
         }
         _loc10_ += 1;
      }
      _loc9_ += 1;
   }
};
_autoRebuildMc = _root.createEmptyMovieClip("_autoRebuildMc",_root.getNextHighestDepth());
_autoRebuildMc._lastSceneName = "";
_autoRebuildMc._lastArrayRef = undefined;
_autoRebuildMc._delayFrames = 0;
_autoRebuildMc.onEnterFrame = function()
{
   if(_root.{{OBJ_SCENE}} == undefined || _root.{{OBJ_SCENE}}.{{SCENE_CLIP}} == undefined)
   {
      return undefined;
   }
   var _loc3_ = _root.{{OBJ_SCENE}}.{{SCENE_CLIP}}._name;
   var _loc4_ = _root.{{OBJ_SCENE}}.{{TERRAIN_ARRAY}};
   if(_loc3_ != this._lastSceneName || _loc4_ != this._lastArrayRef)
   {
      this._lastSceneName = _loc3_;
      this._lastArrayRef = _loc4_;
      this._delayFrames = 5;
   }
   if(this._delayFrames > 0)
   {
      this._delayFrames -= 1;
      if(this._delayFrames == 0 && _root.{{OBJ_SCENE}}.{{SCENE_CLIP}}.mcWalkRange != undefined && _root.{{OBJ_SCENE}}.{{TERRAIN_ARRAY}} != undefined)
      {
         _root._rebuildTerrain();
      }
   }
};
