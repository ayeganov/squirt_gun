define(
function()
{
    /**
     * This class counts number of frames in the last second.
     */
    function FPSCounter()
    {
        var self = this;

        var get_seconds = function()
        {
            return Math.floor(_.now() / 1000);
        };

        var init = function()
        {
            self._this_sec = get_seconds();
            self._fps = 0;
            self._cur_fps = 0;
        };

        self.count_frame = function()
        {
            var cur_sec = get_seconds();
            if(cur_sec === self._this_sec)
            {
                ++self._cur_fps;
            }
            else
            {
                self._fps = self._cur_fps;
                self._cur_fps = 1;
                self._this_sec = cur_sec;
            }
        };

        self.get_fps = function()
        {
            return self._fps;
        };

        init();
    };

    return {
        FPSCounter: FPSCounter
    };
});
